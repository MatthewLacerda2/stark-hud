"""The page tools, as a session sees them: words back, never an exception."""

import pytest
from mcp.server.mcpserver import MCPServer

from core.hub import hub
from hud_mcp.server import build_server
from repositories import board as repo
from tests.hud_mcp.test_tools import Listener, call


@pytest.fixture
def server() -> MCPServer:
    """A server with every tool registered."""
    return build_server()


@pytest.fixture
async def listening() -> Listener:
    """A connected client, dropped again when the test ends."""
    socket = Listener()
    await hub.connect(socket)
    yield socket
    await hub.disconnect(socket)


async def _full_board(server: MCPServer, text: str) -> str:
    """One widget the size of the whole board, on whatever page is showing."""
    await call(server, "add_note", text=text, x=0, y=0, w=32, h=18)
    return repo.list_items()[-1].id


async def test_the_board_cuts_from_one_full_page_to_another(server: MCPServer) -> None:
    """The switch this exists for: two pages, each the size of the whole board."""
    ordinary = await _full_board(server, "the usual")
    await call(server, "show_page", page="planning")
    planning = await _full_board(server, "planning")

    assert repo.get(ordinary).page == "main"
    assert repo.get(planning).page == "planning"

    message = await call(server, "show_page")
    assert "Showing page 'main' — 1 widget on it." in message
    assert "'planning'" in message


async def test_a_page_change_is_one_event(listening: Listener, server: MCPServer) -> None:
    """Every widget of the old page goes and every one of the new arrives in the
    same frame, or the television deals them out one at a time."""
    await _full_board(server, "the usual")
    listening.messages.clear()

    await call(server, "show_page", page="planning")

    assert listening.events() == ["board.arranged"]
    sent = listening.messages[0]["data"]
    assert sent["showing"] == "planning"
    # The board whole, not the page: the browser keeps every widget and draws
    # the ones whose page is showing, which is the rule the server keeps too.
    assert [i["id"] for i in sent["items"]] == [i.id for i in repo.list_items()]


async def test_board_status_says_which_page_and_what_else_is_here(server: MCPServer) -> None:
    """A board reporting nothing on it is not a board with nothing on it."""
    await _full_board(server, "the usual")
    await call(server, "show_page", page="planning")

    status = await call(server, "board_status")
    assert "0 items" in status
    assert "Showing page 'planning'." in status
    assert "'main' (1)" in status


async def test_a_widget_says_when_it_is_on_a_page_that_is_not_showing(
    server: MCPServer,
) -> None:
    """It is listed because it still exists and still takes writes by key."""
    await call(server, "add_note", text="here", x=0, y=0, w=4, h=3)
    await call(server, "show_page", page="planning")

    assert "[on page 'main', not showing]" in await call(server, "list_items")


async def test_moving_a_widget_to_another_page(server: MCPServer) -> None:
    """A widget that belongs on a screen it was not built on."""
    note = await _full_board(server, "the usual")

    message = await call(server, "move_to_page", item_ids=[note], page="planning")
    assert "1 widgets are on page 'planning' now" in message
    assert repo.get(note).page == "planning"
    assert "0 items" in await call(server, "board_status")


async def test_a_move_that_will_not_fit_is_refused_whole(server: MCPServer) -> None:
    """Nothing is shoved aside on the far page either."""
    await call(server, "show_page", page="planning")
    await _full_board(server, "planning")
    await call(server, "show_page")
    note = await _full_board(server, "the usual")

    message = await call(server, "move_to_page", item_ids=[note], page="planning")
    assert "would be in the same place" in message
    assert repo.get(note).page == "main"
