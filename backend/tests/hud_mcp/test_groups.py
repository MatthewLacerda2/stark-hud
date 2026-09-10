"""The group tools, as a session sees them: words back, never an exception."""

import pytest
from mcp.server.mcpserver import MCPServer

from hud_mcp.server import build_server
from repositories import board as repo
from tests.hud_mcp.test_tools import call


@pytest.fixture
def server() -> MCPServer:
    """A server with every tool registered."""
    return build_server()


async def _two_notes(server: MCPServer) -> list[str]:
    """Two notes on the board, and their ids."""
    await call(server, "add_note", text="one", x=0, y=0, w=4, h=3)
    await call(server, "add_note", text="two", x=20, y=10, w=4, h=3)
    return [i.id for i in repo.list_items()]


async def test_grouping_moves_nothing(server: MCPServer) -> None:
    """A group starts open, and an open group is a bracket rather than a pane."""
    ids = await _two_notes(server)
    message = await call(server, "group_items", item_ids=ids)

    assert "Grouped 2 widgets" in message
    assert [(i.x, i.y) for i in repo.list_items() if i.id in ids] == [(0, 0), (20, 10)]


async def test_folding_and_unfolding_is_a_round_trip(server: MCPServer) -> None:
    """The widgets come back where they were, which is the whole promise."""
    ids = await _two_notes(server)
    await call(server, "group_items", item_ids=ids)
    group = next(i for i in repo.list_items() if i.payload.kind == "group")

    assert "Folded" in await call(server, "fold_group", group_id=group.id)
    assert "folded away inside" in await call(server, "list_items")

    assert "Unfolded" in await call(server, "unfold_group", group_id=group.id)
    assert [(i.x, i.y) for i in repo.list_items() if i.id in ids] == [(0, 0), (20, 10)]


async def test_a_refusal_names_what_is_in_the_way(server: MCPServer) -> None:
    """The caller cannot see the board, so "no" on its own is useless to it."""
    ids = await _two_notes(server)
    await call(server, "group_items", item_ids=ids)
    group = next(i for i in repo.list_items() if i.payload.kind == "group")
    await call(server, "fold_group", group_id=group.id)
    await call(server, "add_note", text="squatter", x=20, y=10, w=4, h=3)

    message = await call(server, "unfold_group", group_id=group.id)
    assert "would be in the same place" in message
    assert ids[1] in message


async def test_a_group_will_not_hold_a_group(server: MCPServer) -> None:
    """One level, and the refusal says so rather than quietly nesting."""
    ids = await _two_notes(server)
    await call(server, "group_items", item_ids=ids[:1])
    inner = next(i for i in repo.list_items() if i.payload.kind == "group")
    await call(server, "group_items", item_ids=ids[1:])

    outer = [i for i in repo.list_items() if i.payload.kind == "group"][-1]
    message = await call(server, "add_to_group", group_id=outer.id, item_ids=[inner.id])
    assert "holds widgets, not groups" in message


async def _screen(server: MCPServer, text: str) -> str:
    """A group holding one widget the size of the whole board, and its id."""
    await call(server, "add_note", text=text, x=0, y=0, w=32, h=18)
    note = repo.list_items()[-1]
    await call(server, "group_items", item_ids=[note.id])
    return repo.list_items()[-1].id


async def test_the_board_cuts_from_one_full_screen_to_another(server: MCPServer) -> None:
    """The switch this exists for: two screens, each the size of the whole board."""
    first = await _screen(server, "flight")
    await call(server, "show_group")
    second = await _screen(server, "battle")

    # One at a time is refused, because the room is still the other screen's.
    assert "would be in the same place" in await call(server, "unfold_group", group_id=first)

    message = await call(server, "show_group", group_id=first)
    assert "Showing" in message and "1 group away" in message
    assert [i.payload.text for i in repo.list_items() if i.payload.kind == "note"] == [
        "flight",
        "battle",
    ]
    assert repo.get(second).payload.state == "away"


async def test_board_status_says_where_the_other_screens_went(server: MCPServer) -> None:
    """A board reporting 0 items and 4 screens away is not a board with nothing on it."""
    group = await _screen(server, "flight")
    await call(server, "show_group")

    status = await call(server, "board_status")
    assert "0 items" in status
    assert f"1 group is away and taking no room: {group}" in status
    assert "show_group" in status


async def test_showing_nothing_leaves_what_is_in_no_group(server: MCPServer) -> None:
    """Screens go away; the widgets that belong to no screen are not screens."""
    await _screen(server, "flight")
    await call(server, "show_group")
    await call(server, "add_note", text="loose", x=0, y=0, w=4, h=3)

    assert "Showing no group. 1 widgets on the board." in await call(server, "show_group")
    assert "off the board with" in await call(server, "list_items")
