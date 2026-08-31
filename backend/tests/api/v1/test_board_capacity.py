"""What happens when the board runs out of room."""

from httpx import AsyncClient

NOTE = {"payload": {"kind": "note", "text": "n"}}
ITEMS = "/api/v1/board/items"


async def _fill(client: AsyncClient) -> None:
    """Fill all 96 cells with 16 default-sized notes."""
    for _ in range(16):
        assert (await client.post(ITEMS, json=NOTE)).status_code == 201


async def test_full_board_reports_what_is_free(client: AsyncClient) -> None:
    """A rejected insert tells the caller how much space is left."""
    await _fill(client)
    response = await client.post(ITEMS, json={"payload": {"kind": "video", "path": "/x.mkv"}})
    assert response.status_code == 409
    body = response.json()
    assert body["cells_free"] == 0
    assert body["requested"] == [6, 4]


async def test_freed_slot_is_reused(client: AsyncClient) -> None:
    """Removing an item makes exactly its slot available again."""
    await _fill(client)
    items = (await client.get(ITEMS)).json()
    victim = items[5]
    assert (await client.delete(f"{ITEMS}/{victim['id']}")).status_code == 204
    response = await client.post(ITEMS, json=NOTE)
    assert response.status_code == 201
    replacement = response.json()
    assert (replacement["x"], replacement["y"]) == (victim["x"], victim["y"])
