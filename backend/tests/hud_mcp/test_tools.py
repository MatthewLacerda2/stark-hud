"""The MCP surface: what an agent can call, and what it reads back."""

import pytest
from mcp.server.mcpserver import MCPServer

from core.config import get_settings
from hud_mcp.server import build_server

COLS = get_settings().GRID_COLS
ROWS = get_settings().GRID_ROWS

EXPECTED = {
    "add_box",
    "add_chart",
    "add_image",
    "add_inbox",
    "add_clock",
    "add_feed",
    "show_page",
    "add_list",
    "add_note",
    "add_text",
    "add_video",
    "board_status",
    "clear_background",
    "clear_board",
    "dismiss_notification",
    "list_items",
    "list_notifications",
    "move_item",
    "notify",
    "remove_item",
    "resize_item",
    "set_background",
    "set_style",
    "set_parent",
}


@pytest.fixture
def server() -> MCPServer:
    """A server with every tool registered."""
    return build_server()


async def call(server: MCPServer, name: str, **args: object) -> str:
    """Call a tool and return its text, the way an agent would see it."""
    result = await server.call_tool(name, args)
    return result.content[0].text


async def test_every_tool_is_registered(server: MCPServer) -> None:
    """The catalogue is the contract; a missing tool is a silent regression."""
    assert {t.name for t in await server.list_tools()} == EXPECTED


async def test_adding_reports_where_it_landed(server: MCPServer) -> None:
    """The agent is told the slot, so it can move or remove it later."""
    assert "at (0,0) size 8x4" in await call(server, "add_note", text="hello")
    assert "at (8,0) size 8x4" in await call(server, "add_note", text="second")


async def test_a_full_board_answers_in_words(server: MCPServer) -> None:
    """No exception reaches the agent: it gets something it can act on."""
    for _ in range((COLS // 8) * (ROWS // 6)):
        await call(server, "add_note", text="n", w=8, h=6)
    message = await call(server, "add_note", text="one too many")
    assert "Not added" in message
    assert "board is full" in message


async def test_bad_enum_values_are_explained(server: MCPServer) -> None:
    """A wrong level names the allowed ones rather than failing validation."""
    message = await call(server, "notify", title="done", level="shouty")
    assert "info, success, warn or error" in message


async def test_status_reports_the_largest_free_rectangle(server: MCPServer) -> None:
    """Told before it tries, an agent can pick a size that fits."""
    assert f"Largest free rectangle: {COLS}x{ROWS} at (0,0)" in await call(server, "board_status")
    await call(server, "add_note", text="x", x=0, y=0, w=COLS, h=6)
    expected = f"Largest free rectangle: {COLS}x{ROWS - 6} at (0,6)"
    assert expected in await call(server, "board_status")
