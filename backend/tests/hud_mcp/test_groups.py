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
    # Every blocker, with the size of the overlap: a quarter of a column is
    # something to nudge, a whole widget is something to go back and ask about.
    assert "1 widget is in the room" in message
    assert "is 4x3 into where" in message
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


async def _folded_at_the_corner(server: MCPServer) -> str:
    """A folded group drawn at (0,0), whose second widget wants (20,10) back."""
    ids = await _two_notes(server)
    await call(server, "group_items", item_ids=ids)
    group = next(i for i in repo.list_items() if i.payload.kind == "group")
    await call(server, "fold_group", group_id=group.id)
    return group.id


async def test_putting_something_in_a_folded_groups_room_says_so_at_the_time(
    server: MCPServer,
) -> None:
    """Told while you are still holding it, not at the unfold a week later."""
    group_id = await _folded_at_the_corner(server)

    message = await call(server, "add_note", text="cat video", x=20, y=10, w=4, h=3)

    # Added, not refused: the room is free while the group is folded, and using
    # it is the whole point of folding.
    assert message.startswith("Added")
    assert f"folded group {group_id} will want this room back" in message
    assert "is 4x3 into where" in message


async def test_moving_something_into_that_room_says_so_too(server: MCPServer) -> None:
    """The same answer whichever way the widget got there."""
    group_id = await _folded_at_the_corner(server)
    note = (await call(server, "add_note", text="chores", x=8, y=0, w=4, h=3)).split()[2]

    message = await call(server, "move_item", item_id=note, x=20, y=10)

    assert message.startswith("Moved")
    assert f"folded group {group_id} will want this room back" in message


async def test_a_widget_that_is_in_nobodys_way_is_told_nothing(server: MCPServer) -> None:
    """A line on every add would be a line nobody reads."""
    await _folded_at_the_corner(server)

    message = await call(server, "add_note", text="quiet", x=8, y=0, w=4, h=3)

    assert "will want this room back" not in message


async def test_one_arrange_moves_the_blocker_and_opens_the_group(server: MCPServer) -> None:
    """One call, one cut on the television, rather than a nudge somebody watches."""
    group_id = await _folded_at_the_corner(server)
    note = (await call(server, "add_note", text="cat video", x=20, y=10, w=4, h=3)).split()[2]

    message = await call(
        server,
        "arrange",
        changes=[{"target": note, "x": 26}, {"target": group_id, "folded": False}],
    )

    assert "Rearranged" in message
    assert repo.get(group_id).payload.state == "open"
    assert repo.get(note).x == 26


async def test_an_arrange_that_leaves_the_room_taken_comes_back_in_words(
    server: MCPServer,
) -> None:
    """A session gets a sentence naming every blocker, never an exception."""
    group_id = await _folded_at_the_corner(server)
    note = (await call(server, "add_note", text="cat video", x=20, y=10, w=4, h=3)).split()[2]

    message = await call(server, "arrange", changes=[{"target": group_id, "folded": False}])

    assert "Not unfolded" in message and note in message
    assert repo.get(group_id).payload.state == "folded"
