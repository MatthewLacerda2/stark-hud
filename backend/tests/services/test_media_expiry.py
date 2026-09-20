"""A media widget that finished playing takes itself off the board.

The clock is faked rather than waited on: every test here hands `expire` the
moment it wants it to think it is, which is the difference between a suite that
runs in milliseconds and one nobody would ever run.

What is being pinned is a distinction, not a timer. A film that reached its end
is finished and goes; a film somebody paused halfway is a person who means to
come back and stays, however long they leave it. Everything else below is one of
those two wearing a different hat.
"""

from datetime import UTC, datetime, timedelta

import pytest

from core.config import Settings, get_settings
from core.hub import hub
from repositories import board as repo
from schemas.board import ItemRead, MediaPayload, NotePayload
from schemas.media import Playback, PlaybackState
from services import media as service
from services import uploads
from tests.hud_mcp.test_tools import Listener

HOUR = get_settings().MEDIA_EXPIRY_SECONDS
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
HOURS_AGO = timedelta(seconds=HOUR + 1)


def _media(state: PlaybackState | None = None, ago: float = 0.0) -> ItemRead:
    """A media widget whose last report was `ago` seconds before `NOW`.

    With no state it has never reported at all, which is the widget added while
    no browser was open.
    """
    item = repo.add(MediaPayload(tracks=[{"path": "/music/01 - Highway to Hell.mp3"}]), 0, 0, 6, 4)
    when = NOW - timedelta(seconds=ago)
    playback = Playback(state=state, at=when) if state is not None else None
    return repo.replace(item.model_copy(update={"playback": playback, "created_at": when}))


@pytest.mark.parametrize("state", ["ended", "idle", "failed"])
async def test_a_widget_with_nothing_left_to_play_goes_after_an_hour(state) -> None:
    """The feature: the album finished, and an hour later the slot is free again.

    `failed` is in here by a decision of this branch — a missing file or a codec
    nothing will decode is not going to start working, so the widget is holding
    a slot to show an error nobody is standing in front of.
    """
    item = _media(state, ago=HOUR + 1)
    assert await service.expire(NOW) == [item.id]
    assert repo.get(item.id) is None


@pytest.mark.parametrize("state", ["paused", "playing"])
async def test_a_paused_film_is_still_there_tomorrow(state) -> None:
    """Pausing is meaning to come back, and a day is not a change of mind."""
    item = _media(state, ago=HOUR * 24)
    assert await service.expire(NOW) == []
    assert repo.get(item.id) is not None


async def test_the_hour_has_to_be_up() -> None:
    """A minute short is not an hour, and the widget is still playing to nobody."""
    item = _media("ended", ago=HOUR - 60)
    assert await service.expire(NOW) == []
    assert repo.get(item.id) is not None


async def test_a_new_report_before_the_hour_is_up_saves_the_widget() -> None:
    """Restarting it resets the clock by replacing the playback, and nothing else."""
    item = _media("ended", ago=HOUR - 60)
    played = repo.replace(item.model_copy(update={"playback": Playback(state="playing", at=NOW)}))
    assert service.finished_since(played) is None
    assert await service.expire(NOW + timedelta(seconds=120)) == []


async def test_an_empty_player_nobody_ever_reported_on_is_idle_from_its_birth() -> None:
    """The player added by hand and never filled: nothing is coming to report."""
    item = repo.add(MediaPayload(), 0, 0, 6, 4)
    born = NOW - timedelta(seconds=HOUR + 1)
    repo.replace(item.model_copy(update={"created_at": born}))
    assert await service.expire(NOW) == [item.id]


async def test_a_queue_nobody_has_played_yet_is_waiting_rather_than_finished() -> None:
    """An album queued while the television was off is still there when it goes on.

    This is the branch's other decision. Silence from the browser means no
    browser, not an empty player — and a queue that vanished an hour after
    somebody set it would be this feature causing the complaint it fixes.
    """
    item = _media(ago=HOUR * 24)
    assert service.finished_since(item) is None
    assert await service.expire(NOW) == []
    assert repo.get(item.id) is not None


async def test_a_looping_queue_never_finishes_so_it_never_goes() -> None:
    """It never reaches `ended`, which is the whole reason looping is safe here."""
    item = repo.add(MediaPayload(tracks=[{"path": "/music/side a.mp3"}], loop=True), 0, 0, 6, 4)
    repo.replace(
        item.model_copy(update={"playback": Playback(state="playing", at=NOW - timedelta(days=3))})
    )
    assert await service.expire(NOW) == []


async def test_nothing_but_a_media_widget_is_ever_touched() -> None:
    """A note has no playback to read and is not this feature's business."""
    note = repo.add(NotePayload(text="the bins go out on Tuesday"), 8, 0, 4, 2)
    assert service.finished_since(note) is None
    assert await service.expire(NOW + timedelta(days=30)) == []
    assert repo.get(note.id) is not None


async def test_the_removal_reaches_every_open_screen() -> None:
    """It goes out as an ordinary `item.removed`, so a television redraws itself.

    The point of removing through `services.board` rather than the repository:
    a widget taken off in a loop nobody is watching is exactly the removal that
    must not be the one that forgets to say so.
    """
    item = _media("ended", ago=HOUR + 1)
    socket = Listener()
    await hub.connect(socket)
    try:
        await service.expire(NOW)
    finally:
        await hub.disconnect(socket)
    assert socket.events() == ["item.removed"]
    assert socket.messages[0]["data"] == {"id": item.id}


async def test_the_uploaded_file_goes_with_the_widget(monkeypatch, tmp_path) -> None:
    """An upload nothing else names is swept when its widget expires.

    Nothing in this branch does that: `services.board.remove` already sweeps on
    every media removal (#113), and an expiry is an ordinary removal. This test
    is here because "it comes for free" is a claim, and a claim that is only
    ever read in a docstring is the kind that stops being true.
    """
    monkeypatch.setattr(
        uploads, "get_settings", lambda: Settings(UPLOAD_DIR=str(tmp_path), UPLOAD_GRACE_SECONDS=0)
    )
    folder = tmp_path / "deadbeef"
    folder.mkdir()
    film = folder / "episode 1.mkv"
    film.write_bytes(b"film-bytes")

    item = repo.add(MediaPayload(tracks=[{"path": str(film)}]), 0, 0, 6, 4)
    repo.replace(item.model_copy(update={"playback": Playback(state="ended", at=NOW - HOURS_AGO)}))
    assert await service.expire(NOW) == [item.id]
    assert not film.exists()
