"""Groups: folding a handful of widgets into one, and unfolding them again.

A group is a widget that holds widgets, and membership is ``parent_id`` on the
widgets themselves. Nothing is laid out inside a group and nothing moves into
one — the edge is the whole mechanism.

What a group has that no other widget has is three states, and what they do with
the room the group holds:

- **Open**, the group occupies nothing and its widgets are on the board exactly
  where they always were.
- **Folded**, its widgets come off the board and the group takes their place.
- **Away**, its widgets come off the board and nothing takes their place. That
  is a screen which is not showing, and it is what lets several full-board
  groups exist at once.

That trade is why every one of these is a service rather than a field somebody
sets. Both halves have to happen at once or the board is briefly illegal, and
either half can be refused: a fold has to land somewhere free, and an unfold has
to find the room its widgets left still empty. Nothing is shoved aside to make
either work, which is the answer the board gives everywhere else.

``show`` is the same argument made across several groups at once. One group's
layout fills the board, so the room the next one wants is held by the one that
has it until the same change takes it — which is why turning the board from one
screen to another is one call and could not be several.
"""

from core.config import get_settings
from repositories import board as repo
from schemas.board import GroupPayload, GroupState, ItemRead, Payload, Placement
from services.placement import NoRoomError, illegal

__all__ = [
    "NestedGroupError",
    # Raised from here as often as from anywhere, and imported from here by
    # everything that folds: it lives in ``placement`` because it is about
    # rectangles, and is named here because this is where callers meet it.
    "NoRoomError",
    "NotAGroupError",
    "away",
    "disband",
    "fold",
    "gather",
    "is_group",
    "members",
    "on_board",
    "scatter",
    "show",
    "unfold",
    "weightless",
]


class NotAGroupError(Exception):
    """Raised when something that is not a group is asked to behave like one."""

    def __init__(self, item: ItemRead) -> None:
        self.item = item
        super().__init__(f"{item.id} is a {item.payload.kind}, not a group")


class NestedGroupError(Exception):
    """Raised when a group is asked to hold a group.

    One level, deliberately: a tree of groups is easy to build and hard to hold
    in your head, and no board we want needs the second level.
    """

    def __init__(self, item: ItemRead) -> None:
        self.item = item
        super().__init__(f"{item.id} is itself a group, and a group holds widgets, not groups")


def _grid() -> tuple[int, int]:
    """Return the configured (cols, rows)."""
    settings = get_settings()
    return settings.GRID_COLS, settings.GRID_ROWS


def is_group(item: ItemRead) -> bool:
    """Whether this widget is one that holds widgets."""
    return item.payload.kind == "group"


def _as_group(item: ItemRead) -> GroupPayload | None:
    """The same question, answered with the payload instead of a yes.

    `is_group` gives back a bool, which throws away the one useful thing it
    learned: every read of `.state` after it was a read off a union of thirteen
    payload kinds, twelve of which have no such field. It worked because the
    check had happened; nothing said so.
    """
    return item.payload if isinstance(item.payload, GroupPayload) else None


def _held(items: list[ItemRead]) -> list[tuple[ItemRead, GroupPayload]]:
    """Every group among these widgets, with the payload that says what it is doing."""
    return [(i, held) for i in items if (held := _as_group(i)) is not None]


def _closed(items: list[ItemRead]) -> set[str]:
    """The ids of the groups whose widgets are off the board.

    Folded and away both take the widgets off. What separates them is what
    happens to the room, and that is the next question, not this one.
    """
    return {i.id for i, held in _held(items) if held.state != "open"}


def _shelved(items: list[ItemRead]) -> set[str]:
    """The ids of the groups that are themselves drawn: the folded ones.

    A group away draws nothing. It is the one widget on this board that exists,
    is not folded inside anything, and is still not on the screen.
    """
    return {i.id for i, held in _held(items) if held.state == "folded"}


def away(items: list[ItemRead]) -> list[ItemRead]:
    """The groups that are not showing, oldest first.

    Read by the tools rather than by the board: a caller that cannot see the
    television has no other way to learn that the room it was told is free
    belongs to a screen it could turn to.
    """
    return [i for i, held in _held(items) if held.state == "away"]


def on_board(items: list[ItemRead]) -> list[ItemRead]:
    """The widgets actually taking up room, out of everything that exists.

    An open group is a bracket rather than a pane, so it takes up nothing and
    its widgets take up what they always did. A folded group is the other way
    round. A group that is away is neither: nothing of it is here at all.
    Everything not in a group is simply on the board.
    """
    closed, shelved = _closed(items), _shelved(items)
    return [i for i in items if i.parent_id not in closed and (not is_group(i) or i.id in shelved)]


def weightless(payload: Payload, parent_id: str | None, items: list[ItemRead]) -> bool:
    """Whether a widget of this description takes up no room at all.

    Two things do not: a group that is not folded, and anything inside a group
    that is not open. Neither can collide with anything, so neither has a slot
    found for it or its coordinates checked — a put-away widget's position is a
    note of where it comes back to, and the unfold or the switch back is where
    that is finally tested.
    """
    if payload.kind == "group":
        return payload.state != "folded"
    return parent_id in _closed(items)


def members(group: ItemRead, items: list[ItemRead] | None = None) -> list[ItemRead]:
    """The widgets inside a group, oldest first."""
    return [
        i for i in (items if items is not None else repo.list_items()) if i.parent_id == group.id
    ]


def _refuse(arrangement: list[ItemRead], doing: str) -> None:
    """Raise unless this arrangement is a board that could actually be drawn."""
    why = illegal(arrangement, *_grid())
    if why is not None:
        raise NoRoomError(f"Not {doing}: {why}")


def _where_it_folds(group: ItemRead, inside: list[ItemRead]) -> Placement:
    """Where a group draws once it is closed: where its widgets were.

    The top-left corner of what it holds, at the group's own size. A fold that
    appeared elsewhere on the board would be a fold you have to go and look for,
    and the room it needs has just been vacated by the widgets themselves.
    """
    cols, rows = _grid()
    return Placement(
        x=min(min((i.x for i in inside), default=group.x), max(0.0, cols - group.w)),
        y=min(min((i.y for i in inside), default=group.y), max(0.0, rows - group.h)),
        w=group.w,
        h=group.h,
    )


def _turn(group: ItemRead, state: GroupState, place: Placement | None = None) -> ItemRead:
    """Fold or unfold, but only if the arrangement it produces is a legal board."""
    if not is_group(group):
        raise NotAGroupError(group)
    changed: dict[str, object] = {"payload": group.payload.model_copy(update={"state": state})}
    if place is not None:
        changed |= {"x": place.x, "y": place.y, "w": place.w, "h": place.h}
    turned = group.model_copy(update=changed)

    after = on_board([turned if i.id == group.id else i for i in repo.list_items()])
    _refuse(after, "unfolded" if state == "open" else "folded")
    return repo.replace(turned)


def fold(group: ItemRead) -> ItemRead:
    """Close a group: its widgets come off the board and it takes their place."""
    if not is_group(group):
        raise NotAGroupError(group)
    return _turn(group, "folded", _where_it_folds(group, members(group)))


def unfold(group: ItemRead) -> ItemRead:
    """Open a group: it gives its room back and its widgets return to theirs."""
    return _turn(group, "open")


def _screened(item: ItemRead, showing: str | None) -> ItemRead:
    """This widget as it stands once the board has been turned to ``showing``.

    Anything that is not a group is untouched: a switch changes which widgets
    are drawn, never where any of them is. The layout a screen comes back to is
    the one it left.
    """
    held = _as_group(item)
    if held is None:
        return item
    state: GroupState = "open" if item.id == showing else "away"
    return item.model_copy(update={"payload": held.model_copy(update={"state": state})})


def show(group: ItemRead | None) -> list[ItemRead]:
    """Turn the board to one group: it opens, and every other group goes away.

    Each group carries a whole board's worth of layout, so the room this one
    wants is held by the one that has it until the same change takes it away.
    One group opened at a time would be refused every time, exactly as a swap of
    two widgets is: what has to be legal is the arrangement this produces, not
    any moment inside it.

    Nothing is drawn for the screens that leave and nothing is rebuilt for the
    one that arrives — the widgets kept taking writes while they were away — so
    the board cuts to a screen that is already current.

    ``None`` shows none of them, leaving the board with whatever is in no group.
    Returns the board whole, because the one event this sends carries it whole.
    """
    if group is not None and not is_group(group):
        raise NotAGroupError(group)
    showing = group.id if group is not None else None
    board = [_screened(i, showing) for i in repo.list_items()]
    _refuse(on_board(board), "shown")
    return repo.swap(board)


def _open_enough(item: ItemRead, items: list[ItemRead]) -> None:
    """Raise if this widget is off the board, so its membership cannot change.

    Moving a widget into or out of a group that is not open would be half of the
    trade folding makes: it would vanish from the board with nothing taking its
    place, or appear on it with nothing having made way. Membership changes
    while a group is showing, which is also the only time anybody can see what
    they did.
    """
    if item.parent_id in _closed(items):
        raise NoRoomError(
            f"Not regrouped: {item.id} is inside {item.parent_id}, which is not open. "
            f"Show or unfold that group first."
        )


def gather(group: ItemRead, items: list[ItemRead]) -> list[ItemRead]:
    """Put these widgets in this group, and return them as they now stand."""
    held = _as_group(group)
    if held is None:
        raise NotAGroupError(group)
    if held.state != "open":
        raise NoRoomError(
            f"Not grouped: {group.id} is {held.state}, not open. "
            f"Show or unfold it, then put things in it."
        )
    everything = repo.list_items()
    for item in items:
        if is_group(item):
            raise NestedGroupError(item)
        _open_enough(item, everything)
    return [repo.replace(i.model_copy(update={"parent_id": group.id})) for i in items]


def scatter(items: list[ItemRead]) -> list[ItemRead]:
    """Take these widgets out of whatever group they are in."""
    everything = repo.list_items()
    for item in items:
        _open_enough(item, everything)
    return [repo.replace(i.model_copy(update={"parent_id": None})) for i in items]


def disband(group: ItemRead) -> None:
    """Remove a group, putting its widgets back on the board first.

    Losing a container never silently takes its contents with it, so a group
    that is not open can only be removed while there is still room for what is
    inside it.
    """
    held = _as_group(group)
    if held is None:
        raise NotAGroupError(group)
    if held.state != "open":
        unfold(group)
    repo.remove(group.id)
