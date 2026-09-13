"""Placement takes decimals, on every tool that places anything.

The instructions tell every model that "x=4.5 and w=3.25 are ordinary". Twelve
of the seventeen placing tools typed those as integers, so a model that read the
instructions and did as it was told got a validation error back. The check below
reads the catalogue rather than a list written by hand, so the next tool that
places a widget is covered on the day it is written.
"""

from typing import Any

from hud_mcp.server import build_server
from repositories import board as repo

PLACEMENT = ("x", "y", "w", "h")


def _types(schema: dict[str, Any]) -> set[str]:
    """Every JSON type this property accepts, unwrapping the optional anyOf."""
    branches = schema.get("anyOf", [schema])
    return {branch["type"] for branch in branches if "type" in branch}


async def test_every_placing_tool_takes_decimals() -> None:
    """The board is a space, not 576 slots, and the schemas have to say so."""
    checked = 0
    for tool in await build_server().list_tools():
        properties = tool.input_schema.get("properties", {})
        for name in (n for n in PLACEMENT if n in properties):
            checked += 1
            types = _types(properties[name])
            assert types <= {"number", "null"} and "number" in types, (
                f"{tool.name}.{name} is typed {sorted(types)}; placement takes decimals"
            )
    # A catalogue that had stopped registering the add_ tools would pass vacuously.
    assert checked > 50


async def test_a_widget_lands_on_the_fraction_it_was_given() -> None:
    """End to end through the real server: 4.5 stays 4.5, and is not rounded."""
    args = {"text": "half a column over", "x": 4.5, "y": 2, "w": 3.25, "h": 4}
    result = await build_server().call_tool("add_note", args)
    assert "Not added" not in result.content[0].text
    item = repo.list_items()[0]
    assert (item.x, item.y, item.w, item.h) == (4.5, 2, 3.25, 4)
