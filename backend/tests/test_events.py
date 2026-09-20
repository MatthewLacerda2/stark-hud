"""A change says so once, whichever way in was used.

This is the test the board did not have. Telling the television was done by hand
at every call site, in thirteen files, with the event name typed out beside each
one — so a write path that forgot left the TV showing the old widget, and on a
screen nobody is standing at, that is the worst kind of wrong: it looks fine.

Nothing can check that a broadcast which was never written is missing. What can
be checked is these two, and they are what the arrangement buys:

- the same change made over REST and through MCP produces the **same** event,
  because both go through the same service, and
- it produces **exactly one**, because there is only one place left that sends.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from mcp.server.mcpserver import MCPServer

from core.hub import hub
from hud_mcp.server import build_server
from repositories import board as repo
from tests.hud_mcp.test_tools import Listener, call

ITEMS = "/api/v1/board/items"
NOTE = {"payload": {"kind": "note", "text": "hello"}}


@pytest.fixture
def server() -> MCPServer:
    """A server with every tool registered."""
    return build_server()


@pytest.fixture
async def listening() -> Listener:
    """A connected client, kept for as long as the test runs."""
    socket = Listener()
    await hub.connect(socket)
    yield socket
    await hub.disconnect(socket)


@pytest.fixture
async def rest() -> AsyncClient:
    """An HTTP client on the real app, with nothing mocked.

    Built here rather than taken from ``tests/api/conftest.py`` because this
    file sits beside both surfaces rather than under either.
    """
    from main import app

    assert isinstance(app, FastAPI)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_a_rest_write_says_so_once(rest: AsyncClient, listening: Listener) -> None:
    """Creating over HTTP: one ``item.created``, plus what made it."""
    created = (await rest.post(ITEMS, json=NOTE)).json()

    # `item.origin` rides along with every creation and is not a second change:
    # it is the call, drawn for two seconds beside the widget it made.
    assert listening.events() == ["item.created", "item.origin"]
    assert listening.messages[0]["data"]["id"] == created["id"]


async def test_the_same_write_through_mcp_says_the_same_thing(
    server: MCPServer, listening: Listener
) -> None:
    """The equivalent tool call: the same one event, from the same service."""
    await call(server, "add_note", text="hello")

    assert listening.events() == ["item.created", "item.origin"]
    assert listening.messages[0]["data"]["id"] == repo.list_items()[0].id


async def test_an_update_over_rest_is_one_event(rest: AsyncClient, listening: Listener) -> None:
    """A patch: exactly one ``item.updated`` and nothing else."""
    item_id = (await rest.post(ITEMS, json=NOTE)).json()["id"]
    listening.messages.clear()

    await rest.patch(f"{ITEMS}/{item_id}", json={"x": 8, "y": 4})

    assert listening.events() == ["item.updated"]
    assert listening.messages[0]["data"]["x"] == 8


async def test_the_same_move_through_mcp_is_the_same_one_event(
    server: MCPServer, listening: Listener
) -> None:
    """``move_item`` is a patch by another name, and says exactly what one says."""
    await call(server, "add_note", text="hello")
    item_id = repo.list_items()[0].id
    listening.messages.clear()

    await call(server, "move_item", item_id=item_id, x=8, y=4)

    assert listening.events() == ["item.updated"]
    assert listening.messages[0]["data"]["x"] == 8


async def test_a_removal_is_one_event_from_either_side(
    rest: AsyncClient, server: MCPServer, listening: Listener
) -> None:
    """Both ways of taking a widget off, each saying it once."""
    over_http = (await rest.post(ITEMS, json=NOTE)).json()["id"]
    await call(server, "add_note", text="the other one")
    over_mcp = next(i.id for i in repo.list_items() if i.id != over_http)
    listening.messages.clear()

    await rest.delete(f"{ITEMS}/{over_http}")
    await call(server, "remove_item", item_id=over_mcp)

    assert listening.events() == ["item.removed", "item.removed"]
    assert [m["data"]["id"] for m in listening.messages] == [over_http, over_mcp]


async def test_rearranging_carries_the_board_whole_from_either_side(
    rest: AsyncClient, server: MCPServer, listening: Listener
) -> None:
    """One event per change the TV should see as one change — including the page.

    ``showing`` used to be on the REST arrangement and missing from the MCP one,
    which the frontend reads straight into its state: an ``arrange`` tool call
    left the board not knowing which page it was on.
    """
    await rest.post(ITEMS, json={**NOTE, "x": 0, "y": 0})
    item_id = repo.list_items()[0].id
    listening.messages.clear()

    await rest.post("/api/v1/board/arrange", json={"changes": [{"target": item_id, "x": 8}]})
    await call(server, "arrange", changes=[{"target": item_id, "x": 12}])

    assert listening.events() == ["board.arranged", "board.arranged"]
    for message in listening.messages:
        assert message["data"]["showing"] == repo.showing()
        assert len(message["data"]["items"]) == 1
