"""A file arriving from a browser, and playing once it has.

The end of the round trip is the test worth having: the path that comes back
goes into a media queue untouched, and the track route then serves the bytes
back. That is the claim the whole issue rests on — that nothing downstream of
the endpoint knows a track was uploaded.
"""

from pathlib import Path

import pytest
from httpx import AsyncClient

from core.config import Settings
from services import uploads

ITEMS = "/api/v1/board/items"
UPLOAD = "/api/v1/media/upload"


@pytest.fixture(autouse=True)
def area(monkeypatch, tmp_path):
    """An upload directory of this test's own, so the real one is never written."""
    root = tmp_path / "uploads"
    monkeypatch.setattr(
        uploads,
        "get_settings",
        lambda: Settings(UPLOAD_DIR=str(root), UPLOAD_GRACE_SECONDS=0.0),
    )
    return root


async def _send(client: AsyncClient, name: str, body: bytes):
    """Post a file the way the browser does: the bytes, and the name in the query."""
    return await client.post(UPLOAD, params={"name": name}, content=body)


async def test_an_uploaded_file_queues_and_plays(client: AsyncClient):
    """The whole round trip: bytes in, path back, queue it, bytes out again."""
    sent = await _send(client, "Interstellar.mp4", b"pretend-a-film")
    assert sent.status_code == 201
    got = sent.json()
    assert Path(got["path"]).read_bytes() == b"pretend-a-film"

    body = {"payload": {"kind": "media", "tracks": [{"path": got["path"]}]}}
    item = (await client.post(ITEMS, json=body)).json()
    assert item["payload"]["tracks"][0]["title"] == "Interstellar"

    played = await client.get(f"/api/v1/media/{item['id']}/track/0")
    assert played.status_code == 200
    assert played.content == b"pretend-a-film"
    assert played.headers["content-type"] == "video/mp4"


async def test_a_file_the_board_cannot_play_is_refused(client: AsyncClient, area: Path):
    """The same table a queue is checked against, one step earlier."""
    refused = await _send(client, "holiday-plans.txt", b"nothing to play here")
    assert refused.status_code == 415
    assert "audio or video" in refused.json()["detail"]
    assert not area.exists()


async def test_a_traversing_name_stays_inside_the_upload_directory(client: AsyncClient, area: Path):
    """`../../` addresses nothing: the name is a name by the time it is a path."""
    sent = await _send(client, "../../state/board.hud.mp3", b"bytes")
    landed = Path(sent.json()["path"])
    assert landed.parent.parent == area
    assert landed.name == "board.hud.mp3"


async def test_the_same_film_sent_twice_plays_twice(client: AsyncClient):
    """Two widgets, two files, two sets of bytes, one filename."""
    first = (await _send(client, "episode 1.mkv", b"the-first")).json()
    second = (await _send(client, "episode 1.mkv", b"the-second")).json()
    assert first["path"] != second["path"]
    ids = [
        (
            await client.post(
                ITEMS, json={"payload": {"kind": "media", "tracks": [{"path": one["path"]}]}}
            )
        ).json()["id"]
        for one in (first, second)
    ]
    served = [(await client.get(f"/api/v1/media/{i}/track/0")).content for i in ids]
    assert served == [b"the-first", b"the-second"]


async def test_removing_the_widget_takes_the_upload_with_it(client: AsyncClient, area: Path):
    """The cleanup rule, through the door a person actually uses.

    A file a session named elsewhere would be untouched by this; one that
    arrived here belongs to the widget that named it, and to nothing else.
    """
    got = (await _send(client, "one-watch.mp4", b"bytes")).json()
    body = {"payload": {"kind": "media", "tracks": [{"path": got["path"]}]}}
    item = (await client.post(ITEMS, json=body)).json()
    assert Path(got["path"]).is_file()

    assert (await client.delete(f"{ITEMS}/{item['id']}")).status_code == 204
    assert not Path(got["path"]).exists()
    assert list(area.iterdir()) == []


async def test_clearing_the_board_takes_the_uploads_with_it(client: AsyncClient, area: Path):
    """The other way a queue stops existing."""
    got = (await _send(client, "swept.mp4", b"bytes")).json()
    body = {"payload": {"kind": "media", "tracks": [{"path": got["path"]}]}}
    await client.post(ITEMS, json=body)
    assert (await client.delete(ITEMS)).status_code == 200
    assert list(area.iterdir()) == []


async def test_a_widget_that_is_not_media_leaves_the_uploads_alone(client: AsyncClient):
    """Removing a note is not a queue ending; the film it never held stays.

    The sweep runs on any removal — it costs a directory listing — and what
    decides whether a file goes is whether a queue still names it, not which
    widget happened to be taken off the board.
    """
    got = (await _send(client, "kept.mp4", b"bytes")).json()
    body = {"payload": {"kind": "media", "tracks": [{"path": got["path"]}]}}
    await client.post(ITEMS, json=body)
    note = (await client.post(ITEMS, json={"payload": {"kind": "note", "text": "x"}})).json()
    await client.delete(f"{ITEMS}/{note['id']}")
    assert Path(got["path"]).is_file()
