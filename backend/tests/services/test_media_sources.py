"""Turning what a caller says into a queue, and finding the picture beside it.

The shape these are written against is the one this was built for: a ripped
album in a directory whose name has spaces and an apostrophe in it, with the
track numbers in the filenames and a picture dropped in by whatever ripped it.
"""

from pathlib import Path

from repositories import board as repo
from schemas.board import ItemRead
from schemas.media import MediaPayload
from services import media as service

ALBUM = "AC DC - Greatest Hell's Hits/CD1"


def _item(folder: str) -> ItemRead:
    """A media widget holding that folder's queue, as the board would hold it."""
    payload = MediaPayload(tracks=service.tracks_from([folder]))
    return repo.add(payload, 0, 0, 10, 6, None, False)


def _album(tmp_path: Path, tracks: int = 19) -> Path:
    """A directory shaped like the album this widget was built for."""
    folder = tmp_path / ALBUM
    folder.mkdir(parents=True)
    for n in range(1, tracks + 1):
        (folder / f"{n:02d} - Track {n}.mp3").write_bytes(b"id3")
    (folder / "AlbumArt_{ABC-123}_Large.jpg").write_bytes(b"jpeg")
    (folder / "album.m3u").write_text("not a track")
    return folder


def test_a_directory_is_the_whole_album_in_order(tmp_path: Path) -> None:
    """One string queues nineteen tracks, sorted the way they are numbered."""
    queue = service.tracks_from([str(_album(tmp_path))])
    assert len(queue) == 19
    assert [t.title for t in queue[:2]] == ["01 - Track 1", "02 - Track 2"]
    # The picture and the playlist beside the tracks are not tracks.
    assert all(t.kind == "audio" for t in queue)


def test_a_glob_picks_the_same_files(tmp_path: Path) -> None:
    """`.../CD1/*.mp3` is how a person writes it, so it works too."""
    queue = service.tracks_from([f"{_album(tmp_path)}/*.mp3"])
    assert len(queue) == 19


def test_a_named_file_is_taken_at_its_word(tmp_path: Path) -> None:
    """It may not be there yet; a missing file is a placeholder, not a refusal."""
    queue = service.tracks_from([str(tmp_path / "later.mp3")])
    assert [t.kind for t in queue] == ["audio"]


def test_something_the_browser_cannot_play_is_refused(tmp_path: Path) -> None:
    """Named outright, a file this board cannot play is a mistake worth saying."""
    try:
        service.tracks_from([str(tmp_path / "notes.txt")])
    except ValueError as exc:
        assert "not an audio or video file" in str(exc)
    else:
        raise AssertionError("a text file was accepted into a queue")


def test_the_art_beside_an_album_is_found(tmp_path: Path) -> None:
    """Whatever the ripper called it, as long as it starts the way they all do."""
    folder = _album(tmp_path)
    item = _item(str(folder))
    assert Path(service.art_path(item, 0)).name.startswith("AlbumArt")


def test_an_album_with_no_picture_simply_has_none(tmp_path: Path) -> None:
    """A missing picture is ordinary: the widget draws a symbol instead."""
    folder = tmp_path / "bare"
    folder.mkdir()
    (folder / "one.mp3").write_bytes(b"id3")
    assert service.art_path(_item(str(folder)), 0) is None
