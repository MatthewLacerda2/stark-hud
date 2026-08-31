"""What happens when the board runs out of room."""

from httpx import AsyncClient

from core.config import get_settings

COLS = get_settings().GRID_COLS
ROWS = get_settings().GRID_ROWS

ITEMS = "/api/v1/board/items"
# A size that widgets the grid exactly, so "full" means zero cells left over.
WIDGET_W, WIDGET_H = 8, 6
WIDGET = {"payload": {"kind": "note", "text": "n"}, "w": WIDGET_W, "h": WIDGET_H}


async def _fill(client: AsyncClient) -> int:
    """Widget the whole grid, and return how many items that took."""
    count = (COLS // WIDGET_W) * (ROWS // WIDGET_H)
    for _ in range(count):
        assert (await client.post(ITEMS, json=WIDGET)).status_code == 201
    assert (await client.get("/api/v1/board/status")).json()["cells_free"] == 0
    return count


async def test_full_board_reports_what_is_free(client: AsyncClient) -> None:
    """A rejected insert tells the caller how much space is left."""
    await _fill(client)
    response = await client.post(ITEMS, json={"payload": {"kind": "video", "path": "/x.mkv"}})
    assert response.status_code == 409
    body = response.json()
    assert body["cells_free"] == 0
    assert body["requested"] == [16, 9]


async def test_freed_slot_is_reused(client: AsyncClient) -> None:
    """Removing an item makes exactly its slot available again."""
    await _fill(client)
    victim = (await client.get(ITEMS)).json()[3]
    assert (await client.delete(f"{ITEMS}/{victim['id']}")).status_code == 204

    response = await client.post(ITEMS, json=WIDGET)
    assert response.status_code == 201
    assert (response.json()["x"], response.json()["y"]) == (victim["x"], victim["y"])
