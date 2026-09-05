"""The colour the board writes in."""

from httpx import AsyncClient

INK = "/api/v1/board/ink"
ITEMS = "/api/v1/board/items"


async def test_no_ink_means_the_stylesheet_decides(client: AsyncClient) -> None:
    """Null is the default, not an absence: the page falls back to white at 65%."""
    assert (await client.get(INK)).json() is None


async def test_setting_and_reading_the_ink(client: AsyncClient) -> None:
    response = await client.put(INK, json={"color": "#ffffffa6"})
    assert response.status_code == 200
    assert (await client.get(INK)).json() == {"color": "#ffffffa6"}


async def test_the_ink_may_be_named(client: AsyncClient) -> None:
    """A named colour follows the theme, so it is stored as the variable."""
    await client.put(INK, json={"color": "muted-foreground"})
    assert (await client.get(INK)).json() == {"color": "var(--color-muted-foreground)"}


async def test_a_colour_the_browser_cannot_read_is_refused(client: AsyncClient) -> None:
    assert (await client.put(INK, json={"color": "offwhite"})).status_code == 422


async def test_clearing_the_ink_returns_to_the_default(client: AsyncClient) -> None:
    await client.put(INK, json={"color": "#ffffffa6"})
    assert (await client.delete(INK)).status_code == 204
    assert (await client.get(INK)).json() is None


async def test_clearing_the_board_leaves_the_ink_alone(client: AsyncClient) -> None:
    """The ink is not an item: emptying the board is about what is on it."""
    await client.put(INK, json={"color": "#ffffffa6"})
    await client.post(ITEMS, json={"payload": {"kind": "note", "text": "x"}})

    await client.delete(ITEMS)

    assert (await client.get(ITEMS)).json() == []
    assert (await client.get(INK)).json() == {"color": "#ffffffa6"}


async def test_a_widget_with_its_own_colour_is_not_the_ink(client: AsyncClient) -> None:
    """The ink is the default and never an override."""
    await client.put(INK, json={"color": "#ffffffa6"})
    made = await client.post(
        ITEMS, json={"payload": {"kind": "note", "text": "x"}, "color": "destructive"}
    )
    assert made.json()["color"] == "var(--color-destructive)"
