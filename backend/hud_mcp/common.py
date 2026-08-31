"""Helpers shared by the MCP tools.

Tools run in the same process as the API, so they call the services directly and
broadcast on the same hub. There is no HTTP hop and no second copy of the board.

Placement failures come back as readable text rather than exceptions: the caller
is a model, and "no room, 12 cells free" is something it can act on.
"""

from core.hub import hub
from schemas.board import ItemCreate, ItemRead, Payload
from services import board as service
from services.board import SlotTakenError
from services.placement import BoardFullError


def describe(item: ItemRead) -> str:
    """One line an agent can read back to itself."""
    return f"{item.payload.kind} {item.id} at ({item.x},{item.y}) size {item.w}x{item.h}"


async def add(
    payload: Payload,
    x: int | None = None,
    y: int | None = None,
    w: int | None = None,
    h: int | None = None,
    parent_id: str | None = None,
) -> str:
    """Create an item, broadcast it, and describe what happened."""
    try:
        item = service.create(ItemCreate(payload=payload, x=x, y=y, w=w, h=h, parent_id=parent_id))
    except BoardFullError as exc:
        return (
            f"Not added: {exc}. Free a slot with remove_item, ask for a smaller "
            f"w/h, or call board_status to see the largest free rectangle."
        )
    except SlotTakenError as exc:
        return f"Not added: {exc}. Omit x and y to let the board place it."

    await hub.broadcast("item.created", item.model_dump(mode="json"))
    return f"Added {describe(item)}"
