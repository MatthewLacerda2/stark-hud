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
