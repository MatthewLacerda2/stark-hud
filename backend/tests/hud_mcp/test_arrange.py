"""The batch tool, as a session sees it: words back, never an exception."""

import pytest
from mcp.server.mcpserver import MCPServer

from hud_mcp.server import build_server
from repositories import board as repo
from tests.hud_mcp.test_tools import call


@pytest.fixture
def server() -> MCPServer:
    """A server with every tool registered."""
    return build_server()


async def _full(server: MCPServer) -> list[str]:
    """Four notes widgeting the whole board, and their ids."""
    for y in (0, 9):
        for x in (0, 16):
            await call(server, "add_note", text=f"{x},{y}", x=x, y=y, w=16, h=9)
    return [i.id for i in repo.list_items()]


async def test_a_swap_that_could_not_be_done_one_call_at_a_time(server: MCPServer) -> None:
    """There is nowhere to park either of them, and none is needed."""
    a, b, *_ = await _full(server)

    message = await call(
        server,
        "arrange",
        changes=[{"target": a, "x": 16, "y": 0}, {"target": b, "x": 0, "y": 0}],
    )

    assert "Rearranged" in message
    assert (repo.get(a).x, repo.get(a).y) == (16, 0)
    assert (repo.get(b).x, repo.get(b).y) == (0, 0)


async def test_the_batch_answers_with_the_board_it_produced(server: MCPServer) -> None:
    """Where you most want to know what you got, rather than having to ask."""
    ids = await _full(server)
    message = await call(server, "arrange", changes=[{"target": ids[0], "opacity": 0.4}])

    for item_id in ids:
        assert item_id in message


async def test_a_refusal_is_a_sentence_and_the_board_is_untouched(server: MCPServer) -> None:
    """No exception reaches a session, and nothing half-happened."""
    a, b, *_ = await _full(server)

    message = await call(server, "arrange", changes=[{"target": a, "x": 16, "y": 0}])

    assert "Not rearranged" in message
    assert a in message and b in message
    assert (repo.get(a).x, repo.get(a).y) == (0, 0)


async def test_a_change_the_schema_refuses_comes_back_in_words(server: MCPServer) -> None:
    """A bad field is a sentence a model can act on, not a validation error."""
    ids = await _full(server)
    message = await call(server, "arrange", changes=[{"target": ids[0], "w": -3}])

    assert "Not rearranged" in message
    assert repo.get(ids[0]).w == 16
