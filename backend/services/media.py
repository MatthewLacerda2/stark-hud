"""The rules of the media widget: what is in the queue, and where in it we are.

The queue advances here rather than in the browser. The TV is one of possibly
several things looking at this board and the only one that knows a track ended,
but it is not the place to decide what "ended" means — loop or stop is one rule
and it belongs in one place, where a tool call and a finished track both reach
it and where a test can read it without a browser.

What happens an hour after that is the same rule carried one step further, and
it is at the bottom of this file: a widget with nothing left to play takes
itself off the board. That clock runs here too, for the same reason — there may
be several browsers looking at this board or none at all, and the television may
be off.
"""

import asyncio
import hashlib
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.config import get_settings
from repositories import board as repo
from schemas.board import ItemRead
from schemas.media import (
    MediaAction,
    MediaPayload,
    MediaTrack,
    Playback,
    PlaybackReport,
    PlaybackState,
    kind_of,
    youtube_id,
)
from services import board as board_service
from services import events
from services import tags as tag_reader

logger = logging.getLogger(__name__)

# A picture beside the tracks, in the order we would rather have it. Windows
# Media Player and most rippers leave `AlbumArt_*.jpg`; everything else tends to
# call it cover, folder or front.
_ART_NAMES = ("albumart", "cover", "folder", "front")
_ART_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


def _expand(source: str) -> list[str]:
    """One path, or every playable file under a directory or a glob, in order.

    An album is a directory of nineteen files, and a caller that has to name all
    nineteen in order is a caller that will get the order wrong. So a directory
    is expanded here, sorted by filename, which is what track numbers in
    filenames are for. Anything in it that the browser cannot play is left out —
    a folder of MP3s usually has a picture and a playlist in it too.
    """
    target = Path(source)
    if "*" in source or "?" in source:
        found = target.parent.glob(target.name)
    elif target.is_dir():
        found = target.iterdir()
    else:
        return [source]
    return sorted(str(p) for p in found if p.is_file() and kind_of(str(p)) is not None)


def _stamp(path: str) -> str:
    """A short digest of which file this is, to go in the URL that fetches it.

    The path, plus the file's size and time when there is a file to ask. The
    first makes a replaced queue a set of new URLs; the other two make a
    re-encoded file a new URL as well. A file that is not there yet is stamped by
    name alone and gets the rest next time a queue is built from it.
    """
    marks = [path]
    try:
        found = Path(path).stat()
    except OSError:
        pass
    else:
        marks += [str(found.st_size), str(int(found.st_mtime))]
    return hashlib.blake2s("\0".join(marks).encode(), digest_size=6).hexdigest()


def _local(path: str) -> MediaTrack:
    """One file as a queue entry, named by what the file says about itself.

    The tags are read here, as the queue is built, rather than when a track
    comes round to being played. The queue is built once by a tool call and then
    played by however many browsers are looking at the board, so reading it once
    on the machine that has the files is both the fewest reads and the only
    place the reading can happen at all — a browser is handed the widget's id
    and a place in the queue, never a path.

    An untagged file falls through to what it already had: the filename.
    """
    found = tag_reader.read(path)
    return MediaTrack(
        path=path,
        title=found.title,
        artist=found.artist,
        album=found.album,
        stamp=_stamp(path),
    )


def tracks_from(sources: list[str]) -> list[MediaTrack]:
    """Build a queue from paths, directories, globs and YouTube links, in order.

    A plain file path is taken at its word and not checked: the file may appear
    later, and an item pointing at something that has moved shows a placeholder
    rather than breaking, which is how every other local-file widget behaves.

    A YouTube link is one track and is never expanded — there is no directory on
    this machine to look inside. It is otherwise an entry like any other, so a
    single queue can hold an album and a video from the internet next to each
    other and play straight through them.
    """
    queue: list[MediaTrack] = []
    for source in sources:
        video = youtube_id(source)
        if video is not None:
            queue.append(MediaTrack(youtube=video))
            continue
        queue.extend(_local(path) for path in _expand(source))
    return queue


def _payload(item: ItemRead | None) -> MediaPayload | None:
    """The item's payload when it is a media widget, and ``None`` when it is not."""
    if item is None or not isinstance(item.payload, MediaPayload):
        return None
    return item.payload


def track_path(item: ItemRead, index: int) -> str | None:
    """The file one track names, or ``None`` when there is no such file.

    A YouTube track has none, and that is not an error: nothing about it is
    served from here, so asking this board for its bytes is a 404 in the same
    way asking for track twenty of a nineteen-track album is.
    """
    payload = _payload(item)
    if payload is None or not 0 <= index < len(payload.tracks):
        return None
    return payload.tracks[index].path


def art_path(item: ItemRead, index: int) -> str | None:
    """The album art sitting beside a track, if whoever ripped it left one.

    Nothing is embedded or decoded here: this looks for a picture in the same
    directory, which is where every ripper puts one. An album without one falls
    back to a symbol on the widget, which is a better answer than a blank square.

    A folder usually has several — `AlbumArtSmall.jpg` beside `AlbumArt_{…}_Large.jpg`
    is what Windows Media Player leaves — so the biggest file wins. Sorting by
    name would have picked the thumbnail, which on a television is a smudge.
    """
    path = track_path(item, index)
    if path is None:
        return None
    try:
        beside = [
            p
            for p in Path(path).parent.iterdir()
            if p.is_file() and p.suffix.lower() in _ART_SUFFIXES
        ]
    except OSError:
        return None
    for name in _ART_NAMES:
        named = [p for p in beside if p.stem.lower().startswith(name)]
        if named:
            return str(max(named, key=lambda p: p.stat().st_size))
    return None


def stepped(payload: MediaPayload, delta: int) -> MediaPayload:
    """Move one place through the queue, and say what happens at each end.

    Off the end is the whole point of the loop flag: with it the queue starts
    again from the top, without it the widget goes back to the top and stops, so
    that playing again plays the album rather than its last track.

    Off the front only ever happens by asking, and asking to go back from the
    first track is not asking to stop — so it wraps when looping and stays put
    when it does not.
    """
    # Every one of these lands on a different track, so every one of them starts
    # it at the beginning: where the widget had got to was about the track it is
    # leaving.
    if not payload.tracks:
        return payload.model_copy(update={"index": 0, "playing": False, "seconds": 0.0})
    last = len(payload.tracks) - 1
    nxt = payload.index + delta
    if 0 <= nxt <= last:
        return payload.model_copy(update={"index": nxt, "seconds": 0.0})
    if nxt < 0:
        return payload.model_copy(update={"index": last if payload.loop else 0, "seconds": 0.0})
    if payload.loop:
        return payload.model_copy(update={"index": 0, "seconds": 0.0})
    return payload.model_copy(update={"index": 0, "playing": False, "seconds": 0.0})


def commanded(payload: MediaPayload, action: MediaAction, seconds: float = 0.0) -> MediaPayload:
    """Apply one transport verb. Anything unknown is the caller's to check.

    ``seconds`` is read by ``seek`` and ignored by the rest, which is what makes
    these one verb list rather than a transport tool and a seeking tool.
    """
    if action == "play":
        return payload.model_copy(update={"playing": True})
    if action == "pause":
        return payload.model_copy(update={"playing": False})
    if action == "seek":
        return payload.model_copy(update={"seconds": max(seconds, 0.0)})
    if action == "stop":
        return payload.model_copy(update={"index": 0, "playing": False, "seconds": 0.0})
    return stepped(payload, 1 if action == "next" else -1)


async def report(item: ItemRead, incoming: PlaybackReport) -> ItemRead:
    """Record what the browser says it is doing, and act on a finished track.

    A finished track is the only report that changes anything: it is how a queue
    plays itself through without anybody touching the TV. It is acted on only
    when it is about the track the widget is actually on, so a late report from a
    track we have already left cannot skip the one after it.

    A failed track deliberately does not advance. A queue that walks past a file
    it could not play would overwrite the reason on its next report, and the
    whole point of keeping this is that a missing file or a codec the browser
    refuses says so instead of looking like silence.
    """
    payload = _payload(item)
    if payload is None:
        return item

    track = incoming.track if incoming.track is not None else payload.index
    named = payload.tracks[track] if 0 <= track < len(payload.tracks) else None
    updates: dict[str, object] = {
        "playback": Playback(
            state=incoming.state,
            track=track if named else None,
            title=named.title if named else None,
            error=incoming.error,
        )
    }
    # Where it has got to, and what to do about a track that has finished. Both
    # are only ever true of the track the widget is actually on: a report from
    # one it has already left would otherwise rewind the new one, or skip it.
    moved = payload
    if incoming.seconds is not None and track == payload.index:
        moved = moved.model_copy(update={"seconds": incoming.seconds})
    if incoming.state == "ended" and track == payload.index:
        moved = stepped(moved, 1)
    if moved is not payload:
        updates["payload"] = moved
    written = repo.replace(item.model_copy(update=updates))
    await events.updated(written)
    return written


# What "there is nothing left to play" looks like, in the browser's own words.
#
# `ended` is a queue that ran out. `idle` is one that never had anything in it,
# which is what an empty widget somebody added by hand reports. `failed` is
# here by a decision rather than by the issue: a file that is missing, or in a
# codec nothing on this machine will decode, is not going to start working
# later, and a widget left on the board forever to show an error message that
# nobody is standing in front of wastes the same slot for a worse reason.
#
# The two states deliberately not here are `playing` and `paused`. A paused
# film is a person who means to come back to it, and it is still there tomorrow.
FINISHED: frozenset[PlaybackState] = frozenset({"ended", "idle", "failed"})


def _utc(when: datetime) -> datetime:
    """The same moment with a timezone on it.

    Everything this board writes is UTC-aware already. A `.hud` file is plain
    JSON and invites being edited by hand, and one naive timestamp in it would
    otherwise raise inside the loop below — ending it, quietly, for the life of
    the process.
    """
    return when if when.tzinfo is not None else when.replace(tzinfo=UTC)


def finished_since(item: ItemRead) -> datetime | None:
    """When this widget ran out of things to play, or ``None`` while it has some.

    A widget nobody has reported on at all turns on what is in it. An empty one
    is idle and always was, so its clock starts at its own birth: that is what
    takes the player somebody added and never filled back off the board. One
    with a queue has something to play and no browser has been open to play it,
    which is waiting rather than finished — reading it as idle would mean an
    album queued at three for the evening is gone by four whenever the
    television happens to be off, the same surprise pointing the other way.
    """
    payload = _payload(item)
    if payload is None:
        return None
    if item.playback is None:
        return None if payload.tracks else _utc(item.created_at)
    return _utc(item.playback.at) if item.playback.state in FINISHED else None


def expired(items: list[ItemRead], now: datetime) -> list[ItemRead]:
    """Every media widget that ran out longer ago than the settings allow.

    Anything that restarts playback — a report of `playing`, a new queue, a
    transport command — resets this clock without doing anything about it,
    because it replaces the stored playback and the time is read off that.
    """
    cutoff = now - timedelta(seconds=get_settings().MEDIA_EXPIRY_SECONDS)
    return [item for item in items if (at := finished_since(item)) is not None and at <= cutoff]


async def expire(now: datetime | None = None) -> list[str]:
    """Take the finished widgets off the board. Returns the ids that went.

    Through `services.board.remove`, which is what makes this an ordinary
    removal rather than a special one: every open screen is told through
    `services.events`, and a file that arrived by upload and was named by only
    this queue is swept up with it — that path already does both, and this adds
    nothing to either.
    """
    gone = expired(repo.list_items(), now if now is not None else datetime.now(UTC))
    for item in gone:
        logger.info("media widget %s finished at %s; taking it off", item.id, finished_since(item))
        await board_service.remove(item)
    return [item.id for item in gone]


async def reaper(interval: float) -> None:
    """Look the board over for finished widgets, until cancelled.

    A tick that raises is logged and the loop carries on. The alternative is a
    task that dies on one bad widget and takes the whole feature with it until
    somebody restarts the backend — silently, on a board that runs for days.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await expire()
        except Exception:
            logger.exception("media expiry pass failed")
