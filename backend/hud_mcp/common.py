"""Helpers shared by the MCP tools.

Tools run in the same process as the API, so they call the services directly and
broadcast on the same hub. There is no HTTP hop and no second copy of the board.

Placement failures come back as readable text rather than exceptions: the caller
is a model, and "no room, 12 cells free" is something it can act on.
"""

from core.hub import hub
from repositories import board as repo
from schemas.board import ItemCreate, ItemRead, Payload
from services import board as service
from services.board import SlotTakenError
from services.placement import BoardFullError


def _playing(item: ItemRead) -> str:
    """What the browser last said this widget was doing, in a few words.

    Read here rather than behind a tool of its own for the same reason the
    description is: this is the line a session already reads, and a widget that
    is silently failing to play anything should say so where somebody is looking.
    """
    playback = item.playback
    assert playback is not None
    said = f"{playback.state} {playback.title!r}" if playback.title else playback.state
    return f"{said}: {playback.error}" if playback.error else said


def describe(item: ItemRead) -> str:
    """One line an agent can read back to itself.

    The description rides along here rather than waiting behind a tool of its
    own. A session is told to call list_items instead of remembering where
    things are, so this is the line it already reads — and a note it has to ask
    for separately is a note nobody asks for.
    """
    named = f"{item.payload.kind} {item.id}"
    # The key is here because wake_item takes one. A panel a collector feeds has
    # a key and a session has no other way to learn it.
    if item.key:
        named = f"{named} keyed {item.key!r}"
    line = f"{named} at ({item.x},{item.y}) size {item.w}x{item.h}"
    if item.playback is not None:
        line = f"{line} [{_playing(item)}]"
    return f"{line} — {item.description}" if item.description else line


async def add(
    payload: Payload,
    x: int | None = None,
    y: int | None = None,
    w: int | None = None,
    h: int | None = None,
    parent_id: str | None = None,
    description: str | None = None,
) -> str:
    """Create an item, broadcast it, and describe what happened."""
    try:
        item = service.create(
            ItemCreate(
                payload=payload, x=x, y=y, w=w, h=h, parent_id=parent_id, description=description
            )
        )
    except BoardFullError as exc:
        return (
            f"Not added: {exc}. Free a slot with remove_item, ask for a smaller "
            f"w/h, or call board_status to see the largest free rectangle."
        )
    except SlotTakenError as exc:
        return f"Not added: {exc}. Omit x and y to let the board place it."

    await hub.broadcast("item.created", item.model_dump(mode="json"))
    return f"Added {describe(item)}"


def find(target: str) -> ItemRead | None:
    """The item with this id, or else the panel with this key.

    A caller has one or the other and rarely both: an id comes back from the
    tool that made the widget, a key is what a repeating writer calls its panel.
    Ids are tried first because they are unique by construction and keys only by
    convention.
    """
    return repo.get(target) or repo.get_by_key(target)


async def wake(item: ItemRead) -> None:
    """Say that this widget is about to be written to, before writing it.

    Its own event rather than a flag on the write, because the whole value is in
    arriving earlier than the write does. A widget told it is coming can
    acknowledge while the answer is still being worked out; one told alongside
    the answer has nothing left to acknowledge.
    """
    await hub.broadcast("item.waking", {"id": item.id})
