"""The MCP surface: what an agent can call, and what it reads back."""

import pytest
from mcp.server.mcpserver import MCPServer

from hud_mcp.server import build_server

EXPECTED = {
    "add_box",
    "add_chart",
    "add_image",
    "add_note",
    "add_text",
    "add_video",
    "board_status",
    "clear_background",
    "clear_board",
    "list_items",
    "move_item",
    "notify",
    "remove_item",
    "resize_item",
    "set_background",
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
    assert "at (0,0) size 3x2" in await call(server, "add_note", text="hello")
    assert "at (3,0) size 3x2" in await call(server, "add_note", text="second")


async def test_a_full_board_answers_in_words(server: MCPServer) -> None:
    """No exception reaches the agent: it gets something it can act on."""
    for _ in range(16):
        await call(server, "add_note", text="n")
    message = await call(server, "add_note", text="one too many")
    assert "Not added" in message
    assert "board is full" in message


async def test_bad_enum_values_are_explained(server: MCPServer) -> None:
    """A wrong level names the allowed ones rather than failing validation."""
    message = await call(server, "notify", message="done", level="shouty")
    assert "info, success, warn or error" in message


async def test_status_reports_the_largest_free_rectangle(server: MCPServer) -> None:
    """Told before it tries, an agent can pick a size that fits."""
    assert "Largest free rectangle: 12x8 at (0,0)" in await call(server, "board_status")
    await call(server, "add_note", text="x", x=0, y=0, w=12, h=4)
    assert "Largest free rectangle: 12x4 at (0,4)" in await call(server, "board_status")
