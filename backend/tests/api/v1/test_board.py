"""Board API: placement, collisions, and the full-board contract."""

from httpx import AsyncClient

from core.config import get_settings

COLS = get_settings().GRID_COLS
ROWS = get_settings().GRID_ROWS

NOTE = {"payload": {"kind": "note", "text": "hello"}}
ITEMS = "/api/v1/board/items"


async def _post(client: AsyncClient, body: dict) -> tuple[int, dict]:
    """POST an item and return (status, json)."""
    response = await client.post(ITEMS, json=body)
    return response.status_code, response.json()


async def test_empty_board_reports_whole_grid_free(client: AsyncClient) -> None:
    """A fresh board offers the entire grid as one rectangle."""
    body = (await client.get("/api/v1/board/status")).json()
    assert body["cells_used"] == 0
    assert body["largest_free_rect"] == {"x": 0, "y": 0, "w": COLS, "h": ROWS}


async def test_note_without_coordinates_is_auto_placed(client: AsyncClient) -> None:
    """Omitting x/y places the item at the first free slot with a default size."""
    code, item = await _post(client, NOTE)
    assert code == 201
    assert (item["x"], item["y"]) == (0, 0)
    assert (item["w"], item["h"]) == (8, 4)  # the default size for a note


async def test_explicit_placement_is_honoured(client: AsyncClient) -> None:
    """Given coordinates are used verbatim."""
    code, item = await _post(client, {**NOTE, "x": 6, "y": 4, "w": 4, "h": 3})
    assert code == 201
    assert (item["x"], item["y"], item["w"], item["h"]) == (6, 4, 4, 3)


async def test_collision_is_rejected(client: AsyncClient) -> None:
    """A second item cannot claim an occupied slot."""
    await _post(client, {**NOTE, "x": 0, "y": 0})
    code, body = await _post(client, {**NOTE, "x": 0, "y": 0})
    assert code == 409
    assert "taken or out of bounds" in body["detail"]


async def test_placement_outside_the_grid_is_rejected(client: AsyncClient) -> None:
    """An item may not hang off the right edge."""
    code, _ = await _post(client, {**NOTE, "x": COLS - 1, "y": 0, "w": 3, "h": 1})
    assert code == 409
