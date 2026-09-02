"""What a queue learns from the files themselves, and what it does without them.

A filename is the only name a path carries, and it says nothing about who is
playing. The album this was built against — nineteen AC/DC tracks ripped by
Windows Media Player — has every one of `title`, `artist`, `albumartist` and
`album` filled in, which is the case worth getting right. The cases worth
guarding are the other ones: an untagged file, a file that is not really audio,
and a file that is not there yet. None of those may print a placeholder.

The fixtures are real MP3s rather than the `b"id3"` stand-ins elsewhere in these
tests, because a tag reader that is handed something unparseable is exactly what
the last two cases are about — so the first ones have to be parseable.
"""

from pathlib import Path

import mutagen

from services import media as service
from services import tags as tag_reader

# One MPEG-1 Layer III frame of silence. Twenty of them is the smallest thing
# mutagen will agree is an MP3, and that is all a tag has to hang off.
_FRAME = b"\xff\xfb\x90\x00" + b"\x00" * 413


def _mp3(path: Path, **written: str) -> Path:
    """A playable MP3 carrying exactly the tags named, and no others."""
    path.write_bytes(_FRAME * 20)
    if written:
        audio = mutagen.File(str(path), easy=True)
        audio.add_tags()
        for name, value in written.items():
            audio[name] = value
        audio.save()
    return path


def test_a_track_is_named_by_its_tags_not_its_filename(tmp_path: Path) -> None:
    """`07. Back In Black.mp3` knows a number and a title; the file knows the rest."""
    path = _mp3(
        tmp_path / "07. Back In Black.mp3",
        title="Back In Black",
        artist="ACDC",
        album="Greatest Hell's Hits (CD1)",
    )
    (track,) = service.tracks_from([str(path)])
    assert track.title == "Back In Black"
    assert track.artist == "ACDC"
    assert track.album == "Greatest Hell's Hits (CD1)"


def test_a_file_with_no_tags_still_has_a_name(tmp_path: Path) -> None:
    """The filename it always had, and nothing invented to sit beside it."""
    (track,) = service.tracks_from([str(_mp3(tmp_path / "07. Back In Black.mp3"))])
    assert track.title == "07. Back In Black"
    assert track.artist is None
    assert track.album is None


def test_a_tag_that_is_there_but_blank_is_not_an_answer(tmp_path: Path) -> None:
    """A ripper leaves empty frames behind; a widget must not draw a label for one."""
    path = _mp3(tmp_path / "08. Who Made Who.mp3", title="Who Made Who", artist="   ")
    assert tag_reader.read(str(path)) == tag_reader.Tags(title="Who Made Who")


def test_the_album_artist_answers_when_the_track_does_not(tmp_path: Path) -> None:
    """A compilation names both; only one of them is ever missing."""
    path = _mp3(tmp_path / "01. Thunderstruck.mp3", albumartist="AC/DC")
    assert tag_reader.read(str(path)).artist == "AC/DC"


def test_something_that_is_not_really_audio_is_simply_untagged(tmp_path: Path) -> None:
    """Three bytes with an mp3 suffix reads as nothing, not as a failure."""
    unreadable = tmp_path / "sleeve.mp3"
    unreadable.write_bytes(b"id3")
    assert tag_reader.read(str(unreadable)) == tag_reader.Tags()


def test_a_file_that_is_not_there_yet_is_queued_anyway(tmp_path: Path) -> None:
    """Queuing a path is taken at its word, so reading its tags cannot refuse it."""
    (track,) = service.tracks_from([str(tmp_path / "later.mp3")])
    assert track.title == "later"
    assert (track.artist, track.album) == (None, None)
