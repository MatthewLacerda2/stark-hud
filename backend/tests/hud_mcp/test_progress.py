"""The progress bar: what a session can put on the board, and what it is refused."""

import pytest
from mcp.server.mcpserver import MCPServer
from pydantic import ValidationError

from hud_mcp.server import build_server
from repositories import board as repo
from schemas.board import ItemCreate, ProgressPayload


@pytest.fixture
def server() -> MCPServer:
    """A server with every tool registered."""
    return build_server()


async def call(server: MCPServer, name: str, **args: object) -> str:
    """Call a tool and return its text, the way an agent would see it."""
    return (await server.call_tool(name, args)).content[0].text


def only() -> ProgressPayload:
    """The one progress payload on the board."""
    payload = repo.list_items()[0].payload
    assert isinstance(payload, ProgressPayload)
    return payload


async def test_a_bar_told_only_its_value_runs_from_zero_to_a_hundred(
    server: MCPServer,
) -> None:
    """The defaults are a percentage, with the icon at the start and no colours."""
    await call(server, "add_progress", value=40)
    bar = only()
    assert (bar.min, bar.max, bar.value) == (0, 100, 40)
    assert bar.icon_side == "start"
    assert bar.color is None and bar.unfilled is None
    assert bar.min_label is None and bar.max_label is None


async def test_a_bar_keeps_its_labels_and_its_icon_side(server: MCPServer) -> None:
    """An empty label is kept as empty: that is how an end is hidden."""
    await call(
        server,
        "add_progress",
        value=3,
        max=7,
        min_label="",
        max_label="Friday",
        icon="rocket",
        icon_side="end",
    )
    bar = only()
    assert (bar.min_label, bar.max_label, bar.icon_side) == ("", "Friday", "end")


async def test_a_bar_whose_ends_are_the_wrong_way_round_is_refused(
    server: MCPServer,
) -> None:
    """There is no bar to draw, and the caller is told in a sentence."""
    message = await call(server, "add_progress", value=5, min=10, max=10)
    assert message.startswith("Not added:")
    assert "greater than min" in message
    assert repo.list_items() == []


async def test_a_value_past_either_end_is_kept_rather_than_refused(
    server: MCPServer,
) -> None:
    """A run that overshot its budget is finished, not malformed."""
    await call(server, "add_progress", value=130)
    assert only().value == 130


async def test_an_icon_side_that_is_not_one_is_refused(server: MCPServer) -> None:
    """Refused by the tool, in words, rather than by the model as a stack trace."""
    message = await call(server, "add_progress", value=1, icon_side="left")
    assert message == "Not added: icon_side must be start or end (got 'left')"


def test_a_bar_arrives_over_the_api_as_a_payload_like_any_other() -> None:
    """A panel writes it by key, so it has to validate from plain JSON."""
    item = ItemCreate.model_validate(
        {"payload": {"kind": "progress", "value": 1, "max": 2, "color": "success"}}
    )
    assert isinstance(item.payload, ProgressPayload)
    with pytest.raises(ValidationError):
        ItemCreate.model_validate({"payload": {"kind": "progress", "value": 1, "bar": 2}})
