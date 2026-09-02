"""Writing a panel by name instead of by id.

This is how anything that refreshes finds its own widget again. It used to be a
file on the writer's disk; losing that file left panels on the board that
nothing could claim, and every later write collided with them and was dropped.
"""

from httpx import AsyncClient

KEY = "/api/v1/board/items/by-key/cpu"


def chart(value: int) -> dict:
    """A one-bar chart carrying `value`."""
    return {
        "payload": {
            "kind": "chart",
            "chart": "bar",
            "x_key": "core",
            "series": ["use"],
            "data": [{"core": "0", "use": value}],
        }
    }


async def test_first_write_creates_and_names_it(client: AsyncClient) -> None:
    """A key that is not there yet becomes a new item carrying it."""
    item = (await client.put(KEY, json=chart(10))).json()
    assert item["key"] == "cpu"
    assert len((await client.get("/api/v1/board/items")).json()) == 1


async def test_second_write_updates_the_same_item(client: AsyncClient) -> None:
    """Writing again replaces the contents rather than adding a second widget."""
    first = (await client.put(KEY, json=chart(10))).json()
    second = (await client.put(KEY, json=chart(90))).json()
    assert second["id"] == first["id"]
    assert second["payload"]["data"][0]["use"] == 90
    assert len((await client.get("/api/v1/board/items")).json()) == 1


async def test_a_moved_panel_stays_where_it_was_put(client: AsyncClient) -> None:
    """Refreshing contents must not undo a drag."""
    item = (await client.put(KEY, json={**chart(10), "x": 0, "y": 0, "w": 8, "h": 4})).json()
    await client.patch(f"/api/v1/board/items/{item['id']}", json={"x": 20, "y": 10})

    refreshed = (await client.put(KEY, json=chart(50))).json()
    assert (refreshed["x"], refreshed["y"]) == (20, 10)
    assert refreshed["payload"]["data"][0]["use"] == 50


async def test_position_is_ignored_after_the_first_write(client: AsyncClient) -> None:
    """A refresher sends the same body forever; only the first placement counts.

    Otherwise every update would drag the widget back to where the config says.
    """
    placed = {**chart(10), "x": 0, "y": 0, "w": 8, "h": 4}
    first = (await client.put(KEY, json=placed)).json()
    await client.patch(f"/api/v1/board/items/{first['id']}", json={"x": 20, "y": 10})

    again = (await client.put(KEY, json=placed)).json()
    assert (again["x"], again["y"]) == (20, 10)


async def test_a_panel_keeps_its_description_through_a_refresh(client: AsyncClient) -> None:
    """The failure this design exists to prevent.

    A panel's payload is rewritten whole every few seconds. A note kept inside
    the payload would be gone on the next pass, so it lives on the item.
    """
    first = (await client.put(KEY, json={**chart(10), "description": "cpu, from the agent"})).json()

    await client.put(KEY, json=chart(20))
    await client.put(KEY, json=chart(30))
    refreshed = (await client.put(KEY, json=chart(40))).json()

    assert refreshed["id"] == first["id"]
    assert refreshed["payload"]["data"][0]["use"] == 40
    assert refreshed["description"] == "cpu, from the agent"
