"""Helpers shared by the MCP tools.

Tools run in the same process as the API, so they call the services directly.
There is no HTTP hop and no second copy of the board — and no broadcasting from
here either: a service announces its own change, and this surface only turns the
result into the sentence a model reads back. See ``services.events``.

Placement failures come back as readable text rather than exceptions: the caller
is a model, and "no room, 12 cells free" is something it can act on.
"""

from mcp_types import ToolAnnotations

from repositories import board as repo
from schemas.board import ItemCreate, ItemRead, Payload
from services import board as service
from services import events, groups, pages
from services.board import SlotTakenError
from services.placement import BoardFullError, cells, crowding, size

# Tools that reach past the board: a path on the host, a file it reads, a URL it
# fetches. `open_world_hint` is MCP's own word for exactly this, and the honest
# metadata for any client. It is also what decides which tools a typed
# instruction may use — `services.command` sends a model only the tools that
# need nothing but the board and the sentence, because a model that has never
# seen this computer cannot name a file on it and should not go looking.
ON_HOST = ToolAnnotations(open_world_hint=True)

# Tools that take something away that cannot be put back. One mistyped sentence
# away from an empty board is worth saying out loud in the metadata, whichever
# model is holding the keys.
DESTRUCTIVE = ToolAnnotations(destructive_hint=True)


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
    # The one thing about a widget's look that is said here, because it is the
    # only one a session is ever asked to put back. A colour or a scale is read
    # off the television; whether a widget has an edge at all is what somebody
    # asked for, and set_style is how it goes back.
    if item.flat:
        line = f"{line} [flat]"
    line = f"{line}{_grouping(item)}{_elsewhere(item)}"
    if item.playback is not None:
        line = f"{line} [{_playing(item)}]"
    return f"{line} — {item.description}" if item.description else line


# How each state of a group reads on the one line a session gets back.
_STATES = {"open": "group", "folded": "folded group"}


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
    return f" [folded away inside {item.parent_id}]"


def _elsewhere(item: ItemRead) -> str:
    """Says so when this widget is on a page the board is not showing.

    Every widget is listed whatever page it is on — a panel has to be findable
    by the thing that writes to it, and it is still taking writes — so without
    this a board of forty widgets showing twelve reads as a board that is broken.
    """
    return "" if item.page == pages.showing() else f" [on page {item.page!r}, not showing]"


def room_wanted(watch: list[str]) -> str:
    """What any of these widgets is now standing in the way of, as a line.

    A folded group's widgets are off the board and their coordinates are only a
    note of where they come back to, so the room is free and using it is the
    whole point of folding. Nothing here refuses that. What this says is that
    the way back is blocked, at the moment it is blocked — before, the only
    moment anybody learned it was the unfold itself, by which time the widget
    in the way had been there long enough for nobody to remember putting it
    there.

    Widgets are named by id or by key, because a batch may name them either way.
    """
    items = repo.list_items()
    shut = groups.folded(items)
    taken = []
    for group in (i for i in items if i.id in shut):
        standing = [
            (comes_back, here, dx, dy)
            for comes_back, here, dx, dy in groups.blocked(group, items)
            if here.id in watch or here.key in watch
        ]
        if standing:
            taken.append(f"folded group {group.id} will want this room back — {crowding(standing)}")
    if not taken:
        return ""
    # A line of its own: what comes before it is one widget's line, or a whole
    # board's worth of them, and this is about neither of those exactly.
    return (
        f"\nHeads up: {'; '.join(taken)}. That is allowed and the room is yours while the "
        f"group is folded, but unfold_group refuses until it is clear — and one arrange can "
        f"move this and unfold in the same call."
    )


def _holding(name: str, items: list[ItemRead]) -> str:
    """One page the board is carrying and is not showing, in a few words.

    Its panels are named, not just counted. A panel is born on the page its
    writer says it belongs to, which may not be the page anybody is looking at,
    and a session driving this board over a wire cannot see the television to
    find out. A count alone says a widget is somewhere and leaves the question
    worth asking — which one, and is it the one I am feeding — unanswered.
    """
    held = f"{len(items)} widget" if len(items) == 1 else f"{len(items)} widgets"
    panels = ", ".join(repr(item.key) for item in items if item.key)
    return f"{name!r} ({held})" if not panels else f"{name!r} ({held}, panels {panels})"


def carried() -> str:
    """Which page is showing and what else this board is holding, as a sentence.

    board_status counts what takes room on one page, because each page has the
    whole grid to itself. That is true, and it reads as half the board having
    vanished unless the report says where the rest of it is and what to call it.
    """
    everything = repo.list_items()
    showing = pages.showing()
    rest = ", ".join(
        _holding(name, [item for item in everything if item.page == name])
        for name in pages.names(everything)
        if name != showing
    )
    line = f" Showing page {showing!r}."
    return line if not rest else f"{line} Also here, drawn by nothing until you turn to it: {rest}."


async def add(
    payload: Payload,
    x: float | None = None,
    y: float | None = None,
    w: float | None = None,
    h: float | None = None,
    parent_id: str | None = None,
    description: str | None = None,
) -> str:
    """Create an item and describe what happened.

    The widget reaches the television from inside ``services.board.create``,
    with whatever call made it, so none of the sixteen ``add_`` tools above this
    has anything to remember.
    """
    try:
        item = await service.create(
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

    return f"Added {describe(item)}{room_wanted([item.id])}"


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
    await events.waking(item.id)


def typed[P: Payload](target: str, kind: type[P]) -> tuple[ItemRead, P] | None:
    """The widget with this id or key, when its payload is the kind asked for.

    One helper for what used to be three that disagreed: a list's, a player's
    and a countdown stack's, of which only the countdown's also accepted a key —
    so a panel a collector feeds could be added to by name but not requeued or
    appended to by name, for no reason anybody had chosen.

    The payload comes back beside the item because the check that it *is* that
    kind happens here, and handing back only the item throws that away: every
    caller would then read ``.items`` or ``.tracks`` off a union of thirteen
    payload kinds, most of which have no such field.
    """
    item = find(target)
    if item is None or not isinstance(item.payload, kind):
        return None
    return item, item.payload
