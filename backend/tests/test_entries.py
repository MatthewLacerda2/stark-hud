"""Adding one line to a widget that keeps its lines, from either way in.

A list somebody keeps and a countdown stack are the two widgets on this board
that are not written whole: they are built up an entry at a time by sessions that
never saw the other entries. That rule used to live inside the MCP tools, so the
agent on the host — which speaks HTTP and has no MCP client — could rewrite a
list whole or leave it alone, and rewriting whole is exactly what a kept list
cannot survive.

So the point of this file is that both surfaces reach the same service: a line
put there by a session and a line put there by the agent land in the same list,
in order, and neither loses the other's.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server.mcpserver import MCPServer

from core.hub import hub
from hud_mcp.server import build_server
from repositories import board as repo
from tests.hud_mcp.test_tools import Listener, call

ITEMS = "/api/v1/board/items"


@pytest.fixture
def server() -> MCPServer:
    """A server with every tool registered."""
    return build_server()


@pytest.fixture
async def rest() -> AsyncClient:
    """An HTTP client on the real app, the way the agent talks to it."""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _list(rest: AsyncClient, key: str = "shopping") -> str:
    """An empty list on the board, keyed the way a panel is."""
    body = {"payload": {"kind": "list", "title": "Shopping", "items": []}}
    return (await rest.put(f"{ITEMS}/by-key/{key}", json=body)).json()["id"]


def _lines(item_id: str) -> list[str]:
    """What the widget holds, as the lines read on the screen."""
    payload = repo.get(item_id).payload
    return [e if isinstance(e, str) else e.title for e in payload.items]


async def test_a_line_from_each_surface_lands_in_the_same_list(
    rest: AsyncClient, server: MCPServer
) -> None:
    """The whole point: neither side has to know what the other put there."""
    item_id = await _list(rest)

    await call(server, "add_to_list", item_id=item_id, title="milk")
    await rest.post(f"{ITEMS}/{item_id}/entries", json={"title": "bread"})
    await call(server, "add_to_list", item_id=item_id, title="eggs")

    assert _lines(item_id) == ["milk", "bread", "eggs"]


async def test_the_agent_can_append_by_the_panel_key_it_knows(rest: AsyncClient) -> None:
    """A repeating writer knows its panel's name and never its id."""
    item_id = await _list(rest, key="todo")

    await rest.post(f"{ITEMS}/todo/entries", json={"title": "call the plumber"})

    assert _lines(item_id) == ["call the plumber"]


async def test_removing_over_http_names_the_line_as_it_reads(
    rest: AsyncClient, server: MCPServer
) -> None:
    """Matched on the text, because that is what is readable from the sofa."""
    item_id = await _list(rest)
    await call(server, "add_to_list", item_id=item_id, title="milk")
    await call(server, "add_to_list", item_id=item_id, title="bread")

    response = await rest.delete(f"{ITEMS}/{item_id}/entries/  MILK ")

    assert response.status_code == 200
    assert _lines(item_id) == ["bread"]


async def test_a_countdown_takes_its_entries_the_same_way(
    rest: AsyncClient, server: MCPServer
) -> None:
    """One route and one service for both kinds of widget that keep their lines."""
    said = await call(server, "add_countdown", title="Tonight")
    item_id = repo.list_items()[0].id
    assert "Added" in said

    body = {"title": "the film", "start": "2026-09-04T20:00"}
    assert (await rest.post(f"{ITEMS}/{item_id}/entries", json=body)).status_code == 200
    await call(
        server, "add_to_countdown", item_id=item_id, title="the train", start="2026-09-05T07:10"
    )

    assert _lines(item_id) == ["the film", "the train"]


async def test_a_countdown_line_without_a_start_is_refused_in_words(rest: AsyncClient) -> None:
    """A countdown counts down to something, and a dropped field is a lie."""
    said = await call(build_server(), "add_countdown", title="Tonight")
    item_id = repo.list_items()[0].id
    assert "Added" in said

    response = await rest.post(
        f"{ITEMS}/{item_id}/entries", json={"title": "nothing in particular"}
    )

    assert response.status_code == 422
    assert "needs a start" in response.json()["detail"]


async def test_a_widget_written_whole_has_nothing_to_append_to(rest: AsyncClient) -> None:
    """Every other widget on this board is rewritten, so this says so."""
    note = (await rest.post(ITEMS, json={"payload": {"kind": "note", "text": "x"}})).json()

    response = await rest.post(f"{ITEMS}/{note['id']}/entries", json={"title": "x"})

    assert response.status_code == 404
    assert "written whole" in response.json()["detail"]


async def test_appending_tells_the_television_once(rest: AsyncClient) -> None:
    """A kept list is still a widget being rewritten, and says so like one."""
    item_id = await _list(rest)
    socket = Listener()
    await hub.connect(socket)
    try:
        await rest.post(f"{ITEMS}/{item_id}/entries", json={"title": "milk"})
    finally:
        await hub.disconnect(socket)

    # A title on its own stays a plain string, so a list of plain lines stays one.
    assert socket.events() == ["item.updated"]
    assert socket.messages[0]["data"]["payload"]["items"] == ["milk"]
