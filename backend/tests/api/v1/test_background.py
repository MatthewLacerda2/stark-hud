"""The looping video behind the grid."""

from pathlib import Path

from httpx import AsyncClient

BG = "/api/v1/board/background"
ITEMS = "/api/v1/board/items"


async def test_a_missing_file_is_refused_up_front(client: AsyncClient) -> None:
    """Unlike an item, a broken background is invisible — so it is checked now."""
    response = await client.put(BG, json={"path": "/no/such/clip.mp4", "blur": True})
    assert response.status_code == 404
    assert (await client.get(BG)).json() is None


async def test_setting_and_serving_a_background(client: AsyncClient, tmp_path: Path) -> None:
    """A real file is accepted and streamed back for the page to play."""
    clip = tmp_path / "loop.mp4"
    clip.write_bytes(b"pretend-this-is-a-video")
    assert (await client.put(BG, json={"path": str(clip), "blur": True})).status_code == 200
    assert (await client.get(BG)).json() == {"path": str(clip), "blur": True}
    assert (await client.get("/api/v1/media/background")).content == b"pretend-this-is-a-video"


async def test_clearing_the_board_leaves_the_background_alone(
    client: AsyncClient, tmp_path: Path
) -> None:
    """The background is not an item: emptying the board is about what is on it."""
    clip = tmp_path / "loop.mp4"
    clip.write_bytes(b"x")
    await client.put(BG, json={"path": str(clip)})
    await client.post(ITEMS, json={"payload": {"kind": "note", "text": "x"}})

    await client.delete(ITEMS)

    assert (await client.get(ITEMS)).json() == []
    assert (await client.get(BG)).json()["path"] == str(clip)


async def test_clearing_the_background_returns_to_the_dark_ground(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Deleting it restores the plain background and stops serving the file."""
    clip = tmp_path / "loop.mp4"
    clip.write_bytes(b"x")
    await client.put(BG, json={"path": str(clip)})
    assert (await client.delete(BG)).status_code == 204
    assert (await client.get(BG)).json() is None
    assert (await client.get("/api/v1/media/background")).status_code == 404
