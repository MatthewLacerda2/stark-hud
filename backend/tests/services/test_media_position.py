"""Where in a track the widget is, and which file that track actually is.

Both of these were found by putting a four-hour film on the board. Where it had
got to lived in the browser and nowhere else, so rebuilding the containers sent
it back to the beginning and there was no way to ask for the third hour at all.
And a track is addressed by the widget's id and a place in the queue, so
replacing the queue left index 0 behind the same URL it had before — with the
browser still holding, and still playing, the file that used to be there.
"""

from pathlib import Path

from repositories import board as repo
from schemas.media import MediaPayload, PlaybackReport, media_type
from services import media as service

FILM = "/mnt/d_drive/Video/A Very Long Film.mkv"
ALBUM = ["/music/one.mp3", "/music/two.mp3"]
# Three hours and six minutes in, which is where this was asked for.
THIRD_HOUR = 11160.0


def _queue(index: int = 0, seconds: float = 0.0) -> MediaPayload:
    """A two-track queue sitting where the test wants it, however far in."""
    return MediaPayload(tracks=[{"path": p} for p in ALBUM], index=index, seconds=seconds)


def test_a_session_can_say_where_in_a_track_to_start() -> None:
    """The whole point: asking for the third hour without touching the browser."""
    moved = service.commanded(_queue(), "seek", THIRD_HOUR)
    assert moved.seconds == THIRD_HOUR
    assert moved.index == 0


def test_where_it_got_to_is_kept_on_the_payload_not_the_report() -> None:
    """The report is what one browser last said; this has to outlive the browser."""
    payload = _queue()
    kept = service.commanded(payload, "seek", THIRD_HOUR)
    # Written where the board is saved and reloaded from, which is what makes a
    # container restart come back to the third hour rather than to zero.
    assert MediaPayload(**kept.model_dump()).seconds == THIRD_HOUR


def test_moving_to_another_track_starts_it_at_its_beginning() -> None:
    """Where it had got to was about the track it is leaving, not this one."""
    assert service.stepped(_queue(seconds=THIRD_HOUR), 1).seconds == 0.0
    assert service.commanded(_queue(index=1, seconds=90), "stop").seconds == 0.0


def test_a_report_from_a_track_already_left_cannot_rewind_this_one() -> None:
    """A tick is in flight while the queue moves on; it is about the old track."""
    item = repo.add(_queue(index=1, seconds=120), 0, 0, 10, 6, None, False)
    said = service.report(item, PlaybackReport(state="playing", track=0, seconds=8.0))
    assert said.payload.seconds == 120


def test_a_replaced_queue_is_a_different_url_for_the_same_index(tmp_path: Path) -> None:
    """Index 0 means another file now, and the browser must not reuse the old one."""
    (tmp_path / "one.mp3").write_bytes(b"first")
    (tmp_path / "two.mp3").write_bytes(b"second")
    was, now = (service.tracks_from([str(tmp_path / name)])[0] for name in ("one.mp3", "two.mp3"))
    assert was.stamp and now.stamp and was.stamp != now.stamp


def test_a_file_rewritten_in_place_is_a_different_url_too(tmp_path: Path) -> None:
    """Same path, different bytes: the size is in the stamp for exactly this."""
    path = tmp_path / "one.mp3"
    path.write_bytes(b"first")
    before = service.tracks_from([str(path)])[0].stamp
    path.write_bytes(b"a rather longer second encode")
    assert service.tracks_from([str(path)])[0].stamp != before


def test_a_stamp_is_a_stamp_and_never_the_path(tmp_path: Path) -> None:
    """A path never appears in a URL, and this is a thing that goes in a URL."""
    stamp = service.tracks_from([FILM])[0].stamp
    assert "Film" not in stamp
    assert stamp.isalnum()


def test_a_matroska_file_is_called_one() -> None:
    """`mimetypes` reads /etc/mime.types and on this machine has never heard of it."""
    assert media_type(FILM) == "video/x-matroska"
    assert media_type("/music/one.mp3") == "audio/mpeg"
    # A picture is not this board's table to keep; the server may guess it.
    assert media_type("/music/folder.jpg") is None
