"""A media widget stops claiming it is playing once the board can see it is not.

The widget #167 was opened about, read off the live board: its record said
`playing` at 21:53 one evening, its payload said the transport was off 125
seconds into a YouTube video, and it was still saying so a day and a half
later. `playing` never expires, so #112's hour could not reach it.

Every test here fakes the clock, as `test_media_expiry.py` beside it does. What
is pinned is a line between two records that look alike: `playing` beside
`playing: false` is a stop nobody was there to confirm, and is settled; `paused`
beside `playing: false` is a film somebody paused halfway, and is left alone
for as long as they leave it.
"""

from datetime import UTC, datetime, timedelta

from core.config import get_settings
from core.hub import hub
from repositories import board as repo
from schemas.board import ItemRead, ItemUpdate, MediaPayload
from schemas.media import Playback, PlaybackReport, PlaybackState
from services import board as board_service
from services import media as media_service
from services import media_expiry as service
from tests.hud_mcp.test_tools import Listener

HOUR = timedelta(seconds=get_settings().MEDIA_EXPIRY_SECONDS)
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
DAY = timedelta(days=1)


def _media(state: PlaybackState, playing: bool, said: datetime) -> ItemRead:
    """A one-video queue 125 seconds in, whose browser last spoke at `said`."""
    item = repo.add(
        MediaPayload(tracks=[{"youtube": "6ZfuNTqbHE8"}], playing=playing, seconds=125.13),
        0,
        0,
        6,
        4,
    )
    record = Playback(state=state, track=0, title="6ZfuNTqbHE8", at=said)
    return repo.replace(item.model_copy(update={"playback": record}))


async def test_a_pause_with_no_page_there_leaves_the_record_saying_playing() -> None:
    """The cause, reproduced: a transport command writes the payload, never the record.

    This is what `control_media` does. With a page drawing the widget, the page
    pauses and reports `paused`; with none, nothing ever moves the record.
    """
    item = repo.add(MediaPayload(tracks=[{"youtube": "6ZfuNTqbHE8"}]), 0, 0, 6, 4)
    played = await media_service.report(item, PlaybackReport(state="playing", seconds=125.13))
    assert isinstance(played.payload, MediaPayload)
    paused = media_service.commanded(played.payload, "pause")
    written = await board_service.update(played, ItemUpdate(payload=paused))
    assert written.playback is not None and written.playback.state == "playing"
    assert service.contradicted(written)


async def test_the_widget_from_the_issue_settles_and_goes_an_hour_later() -> None:
    """Twenty-two hours of `playing` becomes `idle`, and #112's hour then reaches it.

    The hour runs from the tick that noticed, not from the browser's last word:
    that word is twenty-two hours old, and reading the clock off it would take
    the widget off the board the minute it was settled.
    """
    item = _media("playing", playing=False, said=NOW - timedelta(hours=22))
    assert await service.settle(NOW) == [item.id]

    settled = repo.get(item.id)
    assert settled is not None and settled.playback is not None
    assert (settled.playback.state, settled.playback.at) == ("idle", NOW)
    assert (settled.playback.track, settled.playback.title) == (0, "6ZfuNTqbHE8")
    assert settled.payload == item.payload, "where it stopped is kept"

    assert await service.expire(NOW) == []
    assert await service.settle(NOW + HOUR / 2) == [], "settled once; the clock does not move"
    assert await service.expire(NOW + HOUR + timedelta(seconds=1)) == [item.id]


async def test_a_film_genuinely_paused_halfway_is_still_there_tomorrow() -> None:
    """The line this must not cross: #112 decided a paused film is kept.

    A browser saw this one pause and said so. Neither rule touches it — not the
    record, not its time — however many ticks go by.
    """
    said = NOW - DAY
    item = _media("paused", playing=False, said=said)
    for tick in (NOW, NOW + DAY, NOW + 2 * DAY):
        assert await service.settle(tick) == []
        assert await service.expire(tick) == []
    kept = repo.get(item.id)
    assert kept is not None and kept.playback is not None
    assert (kept.playback.state, kept.playback.at) == ("paused", said)


async def test_a_widget_still_meant_to_be_playing_is_left_alone() -> None:
    """Record and payload agree, so there is nothing the server can see is untrue.

    This is a tab closed halfway through a film: the board still wants it
    playing, and the next page to draw it will.
    """
    item = _media("playing", playing=True, said=NOW - 3 * DAY)
    assert not service.contradicted(item)
    assert await service.settle(NOW) == []
    assert await service.expire(NOW) == []


async def test_a_finished_queue_keeps_its_own_clock() -> None:
    """`ended` beside `playing: false` is the queue running out, and already finished.

    Settling it would restart an hour that is nearly over.
    """
    item = _media("ended", playing=False, said=NOW - HOUR + timedelta(minutes=5))
    assert await service.settle(NOW) == []
    assert await service.expire(NOW + timedelta(minutes=6)) == [item.id]


async def test_playing_it_again_within_the_hour_saves_it() -> None:
    """The rescue every finished widget has: a page that plays it says so."""
    item = _media("playing", playing=False, said=NOW - DAY)
    await service.settle(NOW)
    assert isinstance(item.payload, MediaPayload)
    again = media_service.commanded(item.payload, "play")
    current = repo.get(item.id)
    assert current is not None
    written = await board_service.update(current, ItemUpdate(payload=again))
    await media_service.report(written, PlaybackReport(state="playing"))
    assert await service.expire(NOW + HOUR + timedelta(seconds=1)) == []


async def test_the_correction_reaches_every_open_screen() -> None:
    """A rewritten record is announced like any other write, so no page holds the lie."""
    item = _media("playing", playing=False, said=NOW - DAY)
    socket = Listener()
    await hub.connect(socket)
    try:
        await service.settle(NOW)
    finally:
        await hub.disconnect(socket)
    assert socket.events() == ["item.updated"]
    assert socket.messages[0]["data"]["id"] == item.id
    assert socket.messages[0]["data"]["playback"]["state"] == "idle"
