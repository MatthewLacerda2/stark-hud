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
from services import groups
from services.board import SlotTakenError
from services.placement import BoardFullError, cells, size


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
    line = f"{named} at ({cells(item.x)},{cells(item.y)}) size {size(item.w, item.h)}"
    line = f"{line}{_grouping(item)}"
    if item.playback is not None:
        line = f"{line} [{_playing(item)}]"
    return f"{line} — {item.description}" if item.description else line


# How each state of a group reads on the one line a session gets back. Away is
# the one that most needs saying: it draws nothing, so a board of twenty widgets
# showing six is a screen rather than a fault, and nothing else on this line
# would tell anybody that.
_STATES = {"open": "group", "folded": "folded group", "away": "group that is away"}


def _grouping(item: ItemRead) -> str:
    """Whether this widget holds others, or is held — and so whether it is drawn.

    A widget that is off the board has no other way of saying so here: it would
    otherwise read as a widget that is there and simply cannot be seen.
    """
    if item.payload.kind == "group":
        held = len(groups.members(item))
        return f" — a {_STATES[item.payload.state]} of {held} widgets"
    if item.parent_id is None:
        return ""
    parent = repo.get(item.parent_id)
    if parent is None or parent.payload.kind != "group" or parent.payload.state == "open":
        return f" [in group {item.parent_id}]"
    if parent.payload.state == "folded":
        return f" [folded away inside {item.parent_id}]"
    return f" [off the board with {item.parent_id}, which is away]"


def screens() -> str:
    """The groups that are away, as a sentence, or nothing at all when none is.

    board_status counts what takes room, and a group that is away takes none —
    so a board carrying four screens and showing one reports the room of the
    one. That is true, and it reads as three screens having vanished unless the
    report says where they went and what to call them.
    """
    hidden = groups.away(repo.list_items())
    if not hidden:
        return ""
    named = ", ".join(f"{i.id} ({len(groups.members(i))} widgets)" for i in hidden)
    plural = "group is" if len(hidden) == 1 else "groups are"
    return (
        f" {len(hidden)} {plural} away and taking no room: {named}. "
        f"show_group turns the board to one of them."
    )


async def add(
    payload: Payload,
    x: float | None = None,
    y: float | None = None,
    w: float | None = None,
    h: float | None = None,
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
