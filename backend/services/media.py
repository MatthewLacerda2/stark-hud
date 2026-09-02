"""The rules of the media widget: what is in the queue, and where in it we are.

The queue advances here rather than in the browser. The TV is one of possibly
several things looking at this board and the only one that knows a track ended,
but it is not the place to decide what "ended" means — loop or stop is one rule
and it belongs in one place, where a tool call and a finished track both reach
it and where a test can read it without a browser.
"""

from pathlib import Path

from repositories import board as repo
from schemas.board import ItemRead
from schemas.media import (
    MediaAction,
    MediaPayload,
    MediaTrack,
    Playback,
    PlaybackReport,
    kind_of,
)

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


def tracks_from(sources: list[str]) -> list[MediaTrack]:
    """Build a queue from paths, directories and globs, in the order given.

    A plain file path is taken at its word and not checked: the file may appear
    later, and an item pointing at something that has moved shows a placeholder
    rather than breaking, which is how every other local-file widget behaves.
    """
    paths = [path for source in sources for path in _expand(source)]
    return [MediaTrack(path=path) for path in paths]


def _payload(item: ItemRead | None) -> MediaPayload | None:
    """The item's payload when it is a media widget, and ``None`` when it is not."""
    if item is None or not isinstance(item.payload, MediaPayload):
        return None
    return item.payload


def track_path(item: ItemRead, index: int) -> str | None:
    """The file one track names, or ``None`` when there is no such track."""
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
    if not payload.tracks:
        return payload.model_copy(update={"index": 0, "playing": False})
    last = len(payload.tracks) - 1
    nxt = payload.index + delta
    if 0 <= nxt <= last:
        return payload.model_copy(update={"index": nxt})
    if nxt < 0:
        return payload.model_copy(update={"index": last if payload.loop else 0})
    if payload.loop:
        return payload.model_copy(update={"index": 0})
    return payload.model_copy(update={"index": 0, "playing": False})


def commanded(payload: MediaPayload, action: MediaAction) -> MediaPayload:
    """Apply one transport verb. Anything unknown is the caller's to check."""
    if action == "play":
        return payload.model_copy(update={"playing": True})
    if action == "pause":
        return payload.model_copy(update={"playing": False})
    if action == "stop":
        return payload.model_copy(update={"index": 0, "playing": False})
    return stepped(payload, 1 if action == "next" else -1)


def report(item: ItemRead, incoming: PlaybackReport) -> ItemRead:
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
    if incoming.state == "ended" and track == payload.index:
        updates["payload"] = stepped(payload, 1)
    return repo.replace(item.model_copy(update=updates))
