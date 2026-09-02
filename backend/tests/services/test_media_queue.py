"""What a queue does when a track ends, and what the ends of it mean.

The point of the media widget is that nobody touches it: an album goes on and
plays itself through. That is one rule — what follows this track — and these are
the four answers it can give.
"""

from schemas.media import MediaPayload
from services import media as service

TRACKS = [
    "/music/Greatest Hell's Hits/01 - Highway to Hell.mp3",
    "/music/Greatest Hell's Hits/02 - Back in Black.mp3",
    "/music/Greatest Hell's Hits/03 - Thunderstruck.mp3",
]


def _queue(index: int = 0, loop: bool = False) -> MediaPayload:
    """A three-track queue sitting where the test wants it."""
    return MediaPayload(tracks=[{"path": p} for p in TRACKS], index=index, loop=loop)


def test_a_finished_track_is_followed_by_the_next_one() -> None:
    """The whole feature: an album plays on without anybody touching it."""
    played = service.stepped(_queue(index=0), 1)
    assert played.index == 1
    assert played.playing is True


def test_a_looping_queue_starts_again_from_the_top() -> None:
    """Past the last track, looping means the first one, still playing."""
    wrapped = service.stepped(_queue(index=2, loop=True), 1)
    assert wrapped.index == 0
    assert wrapped.playing is True


def test_a_queue_that_does_not_loop_stops_at_the_end() -> None:
    """It stops, and back at the top: playing again plays the album, not its last track."""
    ended = service.stepped(_queue(index=2), 1)
    assert ended.index == 0
    assert ended.playing is False


def test_going_back_from_the_first_track_is_not_a_way_to_stop() -> None:
    """Asking to go back is never asking to end; it wraps or it stays put."""
    assert service.stepped(_queue(index=0), -1).index == 0
    assert service.stepped(_queue(index=0), -1).playing is True
    assert service.stepped(_queue(index=0, loop=True), -1).index == 2


def test_an_empty_queue_has_nowhere_to_go() -> None:
    """No tracks is not an error, it is a widget with nothing in it yet."""
    empty = service.stepped(MediaPayload(), 1)
    assert (empty.index, empty.playing) == (0, False)


def test_stop_is_pause_and_back_to_the_top() -> None:
    """The difference between stop and pause is where playing again starts."""
    stopped = service.commanded(_queue(index=2), "stop")
    assert (stopped.index, stopped.playing) == (0, False)
    paused = service.commanded(_queue(index=2), "pause")
    assert (paused.index, paused.playing) == (2, False)
    assert service.commanded(paused, "play").playing is True


def test_a_queue_shorter_than_where_we_were_is_not_a_broken_widget() -> None:
    """Replacing nineteen tracks with two costs a track, never the widget."""
    assert MediaPayload(tracks=[{"path": TRACKS[0]}], index=7).index == 0
