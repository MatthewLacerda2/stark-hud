"""The board-ready copy of the background: made once, played when ready, never waited on.

ffmpeg is a stand-in in every test but the last. What is worth pinning down here
is not what ffmpeg does with a video — the last test checks that, with the real
thing, when this machine has it — but the rules around it: that a copy is asked
for once, that the page plays the original until the copy exists and the copy
afterwards, and that a board with no ffmpeg is exactly the board it was before
copies existed.
"""

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from core.config import Settings
from core.hub import hub
from main import app
from schemas.board import Background
from services import background as service

COPY = "/api/v1/media/background/ready"
ORIGINAL = "/api/v1/media/background"


class Listener:
    """A connected page that keeps what it was told about the background."""

    def __init__(self) -> None:
        self.told: list[dict | None] = []

    async def accept(self) -> None:
        """The hub accepts a socket before it remembers it."""

    async def send_json(self, message: dict) -> None:
        if message["event"] == "background.changed":
            self.told.append(message["data"])


@pytest_asyncio.fixture
async def page() -> Listener:
    socket = Listener()
    await hub.connect(socket)
    yield socket
    await hub.disconnect(socket)


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def ffmpeg(monkeypatch, tmp_path):
    """Copies land in a directory of their own, made by a pretend ffmpeg.

    The pretend one holds on until `release` is set, so a test can look at the
    board while a copy is still being made — which is the state the page spends
    the first seconds of every new background in.
    """
    box = SimpleNamespace(calls=[], release=asyncio.Event(), works=True)
    box.folder = tmp_path / "backgrounds"

    async def encode(source: Path, target: Path) -> bool:
        box.calls.append(source)
        await box.release.wait()
        if box.works:
            target.write_bytes(b"copy of " + source.read_bytes())
        return box.works

    monkeypatch.setattr(service, "encode", encode)
    monkeypatch.setattr(service, "get_settings", lambda: Settings(BACKGROUND_DIR=str(box.folder)))
    return box


def _clip(tmp_path: Path, name: str = "loop.mp4") -> Path:
    clip = tmp_path / name
    clip.write_bytes(b"original " + name.encode())
    return clip


async def test_the_original_plays_until_the_copy_is_made(ffmpeg, page, client, tmp_path) -> None:
    """Setting a background answers at once; the board never waits on ffmpeg."""
    clip = _clip(tmp_path)
    shown = await service.set_background(Background(path=str(clip), blur=True))

    assert shown is not None and shown.board_copy is None
    assert page.told == [{"path": str(clip), "blur": True, "board_copy": None}]
    assert (await client.get(ORIGINAL)).content == b"original loop.mp4"
    assert (await client.get(COPY)).status_code == 404

    ffmpeg.release.set()
    await service.settled()


async def test_the_copy_plays_once_it_is_ready(ffmpeg, page, client, tmp_path) -> None:
    """The page is told again when the copy exists, and is served the copy."""
    clip = _clip(tmp_path)
    ffmpeg.release.set()
    await service.set_background(Background(path=str(clip), blur=True))
    await service.settled()

    made = service.shown()
    assert made is not None and made.board_copy is not None
    assert page.told[-1] == {"path": str(clip), "blur": True, "board_copy": made.board_copy}
    assert (await client.get(COPY)).content == b"copy of original loop.mp4"
    assert [p.name for p in ffmpeg.folder.iterdir()] == [made.board_copy]


async def test_a_copy_is_asked_for_once(ffmpeg, tmp_path) -> None:
    """Twice while it is being made, and again once it exists: one encode."""
    background = Background(path=str(_clip(tmp_path)), blur=True)
    await service.set_background(background)
    await service.set_background(background)
    ffmpeg.release.set()
    await service.settled()
    await service.set_background(background)
    service.prepare()
    await service.settled()

    assert len(ffmpeg.calls) == 1


async def test_a_file_replaced_in_place_is_copied_again(ffmpeg, tmp_path) -> None:
    """The copy is named after what it was made from, not only where it lives."""
    clip = _clip(tmp_path)
    ffmpeg.release.set()
    await service.set_background(Background(path=str(clip), blur=True))
    await service.settled()
    clip.write_bytes(b"a different loop, somewhat longer")
    await service.set_background(Background(path=str(clip), blur=True))
    await service.settled()

    assert len(ffmpeg.calls) == 2
    assert len(list(ffmpeg.folder.iterdir())) == 1


async def test_without_ffmpeg_the_board_is_what_it_was(monkeypatch, page, client, tmp_path) -> None:
    """No ffmpeg: no copy, no error, and the original plays blurred by the browser."""
    monkeypatch.setattr(service.shutil, "which", lambda _name: None)
    folder = tmp_path / "backgrounds"
    monkeypatch.setattr(service, "get_settings", lambda: Settings(BACKGROUND_DIR=str(folder)))
    clip = _clip(tmp_path)

    await service.set_background(Background(path=str(clip), blur=True))
    await service.settled()

    assert page.told == [{"path": str(clip), "blur": True, "board_copy": None}]
    assert (await client.get(ORIGINAL)).content == b"original loop.mp4"
    assert (await client.get(COPY)).status_code == 404
    assert list(folder.iterdir()) == []


async def test_a_failed_encode_leaves_nothing_behind(ffmpeg, page, tmp_path) -> None:
    """A half-written copy is never played, and never kept."""
    ffmpeg.works = False
    ffmpeg.release.set()
    await service.set_background(Background(path=str(_clip(tmp_path)), blur=True))
    await service.settled()

    assert len(page.told) == 1
    assert list(ffmpeg.folder.iterdir()) == []


async def test_a_sharp_background_is_played_as_it_is(ffmpeg, tmp_path) -> None:
    """Sharp means the video is the point, so none of its pixels are dropped."""
    ffmpeg.release.set()
    shown = await service.set_background(Background(path=str(_clip(tmp_path)), blur=False))
    await service.settled()

    assert ffmpeg.calls == []
    assert shown is not None and shown.board_copy is None


async def test_only_the_current_backgrounds_copy_is_kept(ffmpeg, page, tmp_path) -> None:
    """Changing background while a copy is made keeps the one on screen, whoever finished last."""
    first = Background(path=str(_clip(tmp_path, "first.mp4")), blur=True)
    second = Background(path=str(_clip(tmp_path, "second.mp4")), blur=True)
    await service.set_background(first)
    await service.set_background(second)
    ffmpeg.release.set()
    await service.settled()

    made = service.shown()
    assert made is not None and made.path == second.path and made.board_copy is not None
    assert [p.name for p in ffmpeg.folder.iterdir()] == [made.board_copy]
    # The page heard about the first background once, when it was set, and
    # never about its copy: that copy was finished for a board no longer showing it.
    assert [m["path"] for m in page.told if m and m["board_copy"]] == [second.path]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs a real ffmpeg")
async def test_the_real_recipe_makes_a_small_slow_silent_copy(tmp_path) -> None:
    """The one test that runs ffmpeg: what comes out is 960x540, 24 fps, no sound."""
    source = tmp_path / "source.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=1",
         "-f", "lavfi", "-i", "sine=d=1", "-shortest", str(source)],
        check=True,
    )  # fmt: skip
    target = tmp_path / "copy.part"

    assert await service.encode(source, target)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate",
         "-of", "json", str(target)],
        check=True, capture_output=True, text=True,
    )  # fmt: skip
    streams = json.loads(probe.stdout)["streams"]
    assert streams == [{"codec_type": "video", "width": 960, "height": 540, "r_frame_rate": "24/1"}]
