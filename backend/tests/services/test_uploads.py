"""Receiving a file, naming it safely, and deleting only what we put there.

Three things here are measured rather than argued, because each of them is a
claim that reads as true in the code and can quietly stop being true:

* the file is never held in memory — `tracemalloc` says so, over sixty-four
  megabytes, which is the size at which buffering would be unmistakable;
* a hostile name cannot address anything outside its own directory — the names
  are the real ones, dots and slashes and a null byte;
* the sweep deletes inside the upload directory and nowhere else, including
  when something inside it points out.
"""

import tracemalloc
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.config import Settings
from repositories import board as repo
from schemas.board import MediaPayload
from services import uploads
from services.uploads import EmptyUpload, UnplayableUpload

CHUNK = 1 << 20
BIG = 64


@pytest.fixture
def area(monkeypatch, tmp_path):
    """An upload directory of this test's own, with the grace window in hand."""
    box = SimpleNamespace(root=tmp_path / "uploads", grace=0.0)
    monkeypatch.setattr(
        uploads,
        "get_settings",
        lambda: Settings(UPLOAD_DIR=str(box.root), UPLOAD_GRACE_SECONDS=box.grace),
    )
    return box


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    """The request body, the way Starlette hands it over."""
    for chunk in chunks:
        yield chunk


def _queue(*paths: str) -> None:
    """Put a media widget on the board whose queue names these files."""
    repo.add(MediaPayload(tracks=[{"path": p} for p in paths]), 0, 0, 6, 4)


async def test_a_file_lands_on_disk_and_says_where(area):
    """The bytes are there, under the name the browser sent, at the path returned."""
    got = await uploads.receive("Cidade de Deus.mkv", _stream(b"film", b"-bytes"))
    assert got.name == "Cidade de Deus.mkv"
    assert got.bytes == 10
    landed = Path(got.path)
    assert landed.read_bytes() == b"film-bytes"
    assert landed.parent.parent == area.root


async def test_two_uploads_of_one_name_are_two_files(area):
    """Neither overwrites the other, and both keep the name they arrived with."""
    first = await uploads.receive("episode 1.mkv", _stream(b"one"))
    second = await uploads.receive("episode 1.mkv", _stream(b"two"))
    assert first.path != second.path
    assert first.name == second.name == "episode 1.mkv"
    assert Path(first.path).read_bytes() == b"one"
    assert Path(second.path).read_bytes() == b"two"


@pytest.mark.parametrize(
    "hostile",
    [
        "../../etc/board.hud.mp4",
        "../../../../../../tmp/escaped.mp4",
        "/etc/passwd.mp4",
        "..\\..\\windows\\evil.mp4",
        "./.././x.mp4",
        "... .mp4",
        "..a.mp4",
        "\x00.mp4",
        "a\x00b/../c.mp4",
        "line\nbreak.mp4",
        "x" * 4000 + ".mp4",
    ],
)
async def test_a_hostile_name_cannot_leave_its_own_directory(area, hostile):
    """Whatever the browser calls it, the file lands one level inside the root."""
    got = await uploads.receive(hostile, _stream(b"bytes"))
    landed = Path(got.path)
    assert landed.parent.parent == area.root
    assert landed.is_file()
    assert got.name == landed.name
    assert not set(got.name) & set("/\\\x00\n")
    assert not got.name.startswith(".")
    assert len(got.name.encode()) <= uploads.MAX_NAME_BYTES + len(".mp4")


# The last two are Python 3.14 reading a name the way a person would not, and
# it is the reading this board wants: leading dots are stripped before the
# suffix is looked for, so `.mp4` is a hidden file with no extension and
# `..........mp4` has none either. The queue reads them the same way — both call
# `Path(...).suffix` — so a name refused here is a name that could not have been
# queued, which is the property that matters.
@pytest.mark.parametrize(
    "refused",
    ["notes.txt", "payload.exe", "noext", "film.mp4.txt", ".mp4.zip", ".mp4", "..........mp4"],
)
async def test_what_the_board_cannot_play_is_refused_before_a_byte_is_written(area, refused):
    """The allowlist is the queue's own, and it answers 415 with the list on it."""
    with pytest.raises(UnplayableUpload) as refusal:
        await uploads.receive(refused, _stream(b"bytes"))
    assert refusal.value.status == 415
    assert ".mkv" in str(refusal.value)
    assert not area.root.exists() or not list(area.root.iterdir())


async def test_an_empty_upload_is_refused_and_leaves_nothing(area):
    """A zero-byte file would queue and then fail to play, blaming the codec."""
    with pytest.raises(EmptyUpload) as refusal:
        await uploads.receive("nothing.mp3", _stream())
    assert refusal.value.status == 422
    assert list(area.root.iterdir()) == []


async def test_nothing_accumulates_while_a_large_file_arrives(area):
    """Sixty-four megabytes through, and Python never holds more than a chunk.

    The measurement, not the argument. Buffering the body — which is what every
    obvious shape of this endpoint does — would put `BIG` megabytes on this peak.
    """
    body = _stream(*(bytes(CHUNK) for _ in range(BIG)))
    tracemalloc.start()
    try:
        got = await uploads.receive("film.mp4", body)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert got.bytes == BIG * CHUNK
    assert peak < 4 * CHUNK, f"held {peak / CHUNK:.1f} MB of a {BIG} MB file"


async def test_a_queued_upload_survives_the_sweep(area):
    """A file a widget still names is not disk used for nothing."""
    got = await uploads.receive("kept.mp3", _stream(b"bytes"))
    _queue(got.path)
    assert uploads.sweep() == []
    assert Path(got.path).is_file()


async def test_an_upload_no_widget_names_is_swept(area):
    """The file, and the directory it had to itself, both go."""
    got = await uploads.receive("orphan.mp3", _stream(b"bytes"))
    assert uploads.sweep() == [str(Path(got.path).parent)]
    assert not Path(got.path).exists()
    assert list(area.root.iterdir()) == []


async def test_an_upload_still_too_young_is_left_alone(area):
    """The gap between the bytes landing and something queueing them.

    Without this window, removing any media widget in that gap deletes a file
    that is a second away from being played.
    """
    area.grace = 3600.0
    got = await uploads.receive("just-arrived.mp3", _stream(b"bytes"))
    assert uploads.sweep() == []
    assert Path(got.path).is_file()


async def test_a_file_a_session_named_elsewhere_is_never_touched(area, tmp_path):
    """The rule that makes this safe: the sweep only ever walks its own directory."""
    album = tmp_path / "music" / "album.mp3"
    album.parent.mkdir()
    album.write_bytes(b"somebody else's file")
    uploads.sweep()
    assert album.is_file()


async def test_a_symlink_out_of_the_upload_directory_loses_only_the_link(area, tmp_path):
    """Whatever put it there, the sweep unlinks it rather than following it."""
    outside = tmp_path / "music"
    outside.mkdir()
    (outside / "album.mp3").write_bytes(b"somebody else's file")
    area.root.mkdir(parents=True, exist_ok=True)
    (area.root / "pointer").symlink_to(outside)
    assert uploads.sweep() == [str(area.root / "pointer")]
    assert (outside / "album.mp3").is_file()


async def test_a_widget_on_another_page_still_holds_its_files(area):
    """Every page counts, not the one showing: page two is still a queue."""
    got = await uploads.receive("elsewhere.mp3", _stream(b"bytes"))
    repo.add(MediaPayload(tracks=[{"path": got.path}]), 0, 0, 6, 4, page="two")
    assert uploads.sweep() == []
    assert Path(got.path).is_file()
