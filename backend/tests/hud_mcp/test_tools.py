"""The MCP surface: what an agent can call, and what it reads back."""

import pytest
from mcp.server.mcpserver import MCPServer

from core.config import get_settings
from hud_mcp.server import build_server
from repositories import board as repo

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
    "add_to_list",
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
    "remove_from_list",
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


async def _a_list(server: MCPServer, *items: str) -> str:
    """Put a list on the board and return its id."""
    await call(server, "add_list", items=list(items), title="todo")
    return repo.list_items()[0].id


async def test_a_list_grows_one_entry_at_a_time(server: MCPServer) -> None:
    """Appending needs no knowledge of what is already there, and loses none of it."""
    item_id = await _a_list(server, "bread")
    assert "2 entries" in await call(server, "add_to_list", item_id=item_id, title="milk")
    assert repo.get(item_id).payload.items == ["bread", "milk"]


async def test_an_entry_with_a_body_keeps_its_shape(server: MCPServer) -> None:
    """A title alone stays a plain line; anything more is stored as an entry."""
    item_id = await _a_list(server, "bread")
    await call(server, "add_to_list", item_id=item_id, title="milk", body="the oat one")
    assert repo.get(item_id).payload.items[-1].body == "the oat one"


async def test_a_list_lets_the_caller_colour_every_part_of_it(server: MCPServer) -> None:
    """Whoever writes the list decides its colours, down to one line's icon."""
    await call(
        server,
        "add_list",
        items=[{"title": "milk", "body": "the oat one", "icon_color": "#00ff8840"}],
        title="todo",
        icon="check",
        title_color="#ffffffbf",
        icon_color="#33ccffaa",
        item_color="#ff8800",
    )
    payload = repo.list_items()[0].payload
    assert (payload.icon, payload.icon_color) == ("check", "#33ccffaa")
    assert payload.items[0].icon_color == "#00ff8840"
    # What the caller said nothing about stays unset, so the widget still decides.
    assert payload.items[0].title_color is None


async def test_a_list_refuses_an_icon_it_could_not_draw(server: MCPServer) -> None:
    """A typo comes back as a sentence naming the vocabulary, not an exception."""
    message = await call(server, "add_list", items=[], title="todo", icon="sparkle")
    assert "is not an icon" in message
    assert repo.list_items() == []


async def test_an_appended_entry_can_carry_its_own_colours(server: MCPServer) -> None:
    """A line added later says as much about itself as one written up front."""
    item_id = await _a_list(server, "bread")
    await call(server, "add_to_list", item_id=item_id, title="milk", title_color="#ff8800")
    entry = repo.get(item_id).payload.items[-1]
    assert (entry.title_color, entry.body) == ("#ff8800", None)


async def test_removing_names_the_lines_it_could_not_find(server: MCPServer) -> None:
    """A session that misremembers the wording is told what is actually there."""
    item_id = await _a_list(server, "bread")
    assert "'bread'" in await call(server, "remove_from_list", item_id=item_id, title="brood")
    assert "0 left" in await call(server, "remove_from_list", item_id=item_id, title=" BREAD ")
    assert repo.get(item_id).payload.items == []


async def test_a_chart_draws_both_axes_unless_told_otherwise(server: MCPServer) -> None:
    """Axes are opt-out, so a caller who says nothing gets the chart they had before."""
    await call(server, "add_chart", chart="bar", data=[{"d": 1}], x_key="d", series=["d"])
    assert repo.list_items()[0].payload.axes == "both"


async def test_a_chart_names_the_axes_it_will_accept(server: MCPServer) -> None:
    """A wrong value comes back as a sentence, the way every other enum does."""
    message = await call(
        server, "add_chart", chart="bar", data=[], x_key="d", series=["d"], axes="off"
    )
    assert "both, x, y or none" in message
    assert repo.list_items() == []
