"""What happens to a media widget once nothing is playing it: it leaves the board.

The same rule as ``services.media`` carried one step further. A queue that ran
out takes itself off the board an hour later, and the clock for that runs here,
on the server, because there may be several browsers looking at this board or
none at all, and the screen may be off.

Its own module rather than the bottom of ``services.media`` because it reads the
widget's record rather than driving its transport, and because the transport
file is at the house limit.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from core.config import get_settings
from repositories import board as repo
from schemas.board import ItemRead
from schemas.media import MediaPayload, Playback, PlaybackState
from services import board as board_service
from services import events

logger = logging.getLogger(__name__)


def _payload(item: ItemRead) -> MediaPayload | None:
    """The item's payload when it is a media widget, and ``None`` when it is not."""
    return item.payload if isinstance(item.payload, MediaPayload) else None


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


def contradicted(item: ItemRead) -> bool:
    """Whether this widget's record says `playing` while its own payload says stop.

    Both cannot be true. The payload is what the board was last told to do and
    the record is what a browser last said it did; this pair is a transport
    turned off — by a `control_media` pause or stop — with no page there to act
    on it and say so. A page that was there would have paused and reported
    `paused`, and the record moves only when a page reports. So it goes on
    saying `playing` for as long as nobody draws the widget, which was a day
    and a half on the live board (#167).

    `paused` beside `playing: false` is the ordinary, correct pair and is not
    this: it is a browser confirming a pause somebody could see.
    """
    payload = _payload(item)
    return (
        payload is not None
        and not payload.playing
        and item.playback is not None
        and item.playback.state == "playing"
    )


async def settle(now: datetime | None = None) -> list[str]:
    """Rewrite every contradicted record to `idle`. Returns the ids it touched.

    `idle` is the page's own word for a player nothing is playing: it is what a
    widget says as it leaves the screen, folded into a group or removed. That is
    what a contradicted record describes — told to stop, and not being drawn by
    anything that could confirm it did.

    The time on the new record is now, the moment the server noticed, not the
    browser's last word. `Playback.at` is the clock the hour is read off, and
    the last word can be days old: keeping it would take a film off the board a
    minute after a session paused it with the tab closed. So the hour runs from
    here, and a page that draws the widget and plays it in that hour replaces
    this record with its own, which is the same rescue every finished widget has.
    """
    when = now if now is not None else datetime.now(UTC)
    touched = []
    for found in [item.id for item in repo.list_items() if contradicted(item)]:
        # Read again, and written before anything is awaited: announcing the
        # last one lets a browser's report land, and that report is the truth.
        item = repo.get(found)
        said = item.playback if item is not None and contradicted(item) else None
        if item is None or said is None:
            continue
        logger.info("media widget %s last said playing at %s; settling it idle", item.id, said.at)
        record = Playback(state="idle", track=said.track, title=said.title, at=when)
        await events.updated(repo.replace(item.model_copy(update={"playback": record})))
        touched.append(item.id)
    return touched


def expired(items: list[ItemRead], now: datetime) -> list[ItemRead]:
    """Every media widget that ran out longer ago than the settings allow.

    Anything that restarts playback resets this clock without doing anything
    about it, because the browser's report of `playing` replaces the stored
    playback and the time is read off that. A transport command alone does not:
    it writes the payload, and the record moves only when a page acts on it.
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

    Each tick settles a contradicted record first and expires second, so a
    record rewritten on this tick starts its hour now rather than going at once.

    A tick that raises is logged and the loop carries on. The alternative is a
    task that dies on one bad widget and takes the whole feature with it until
    somebody restarts the backend — silently, on a board that runs for days.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await settle()
            await expire()
        except Exception:
            logger.exception("media expiry pass failed")
