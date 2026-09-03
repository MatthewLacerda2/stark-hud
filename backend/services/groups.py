"""Groups: folding a handful of widgets into one, and unfolding them again.

A group is a widget that holds widgets, and membership is ``parent_id`` on the
widgets themselves. Nothing is laid out inside a group and nothing moves into
one — the edge is the whole mechanism.

What a group has that no other widget has is two states that trade room with
each other:

- **Open**, the group occupies nothing and its widgets are on the board exactly
  where they always were.
- **Closed**, its widgets come off the board and the group takes their place.

That trade is why folding is a service rather than a field somebody sets. Both
halves have to happen at once or the board is briefly illegal, and either half
can be refused: a fold has to land somewhere free, and an unfold has to find the
room its widgets left still empty. Nothing is shoved aside to make either work,
which is the answer the board gives everywhere else.
"""

from core.config import get_settings
from repositories import board as repo
from schemas.board import ItemRead, Payload, Placement
from services.placement import NoRoomError, illegal

__all__ = [
    "NestedGroupError",
    # Raised from here as often as from anywhere, and imported from here by
    # everything that folds: it lives in ``placement`` because it is about
    # rectangles, and is named here because this is where callers meet it.
    "NoRoomError",
    "NotAGroupError",
    "disband",
    "fold",
    "gather",
    "is_group",
    "members",
    "on_board",
    "scatter",
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


def _shut(items: list[ItemRead]) -> set[str]:
    """The ids of the groups that are currently folded."""
    return {i.id for i in items if is_group(i) and not i.payload.open}


def on_board(items: list[ItemRead]) -> list[ItemRead]:
    """The widgets actually taking up room, out of everything that exists.

    An open group is a bracket rather than a pane, so it takes up nothing and
    its widgets take up what they always did. A closed group is the other way
    round. Everything not in a group is simply on the board.
    """
    shut = _shut(items)
    return [i for i in items if i.parent_id not in shut and (not is_group(i) or i.id in shut)]


def weightless(payload: Payload, parent_id: str | None, items: list[ItemRead]) -> bool:
    """Whether a widget of this description takes up no room at all.

    Two things do not: an open group, and anything inside a closed one. Neither
    can collide with anything, so neither has a slot found for it or its
    coordinates checked — a folded widget's position is a note of where it comes
    back to, and the unfold is where that is finally tested.
    """
    if payload.kind == "group":
        return payload.open
    return parent_id in _shut(items)


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


def _turn(group: ItemRead, opened: bool, place: Placement | None = None) -> ItemRead:
    """Fold or unfold, but only if the arrangement it produces is a legal board."""
    if not is_group(group):
        raise NotAGroupError(group)
    changed: dict[str, object] = {"payload": group.payload.model_copy(update={"open": opened})}
    if place is not None:
        changed |= {"x": place.x, "y": place.y, "w": place.w, "h": place.h}
    turned = group.model_copy(update=changed)

    after = on_board([turned if i.id == group.id else i for i in repo.list_items()])
    _refuse(after, "unfolded" if opened else "folded")
    return repo.replace(turned)


def fold(group: ItemRead) -> ItemRead:
    """Close a group: its widgets come off the board and it takes their place."""
    if not is_group(group):
        raise NotAGroupError(group)
    return _turn(group, False, _where_it_folds(group, members(group)))


def unfold(group: ItemRead) -> ItemRead:
    """Open a group: it gives its room back and its widgets return to theirs."""
    return _turn(group, True)


def _open_enough(item: ItemRead, items: list[ItemRead]) -> None:
    """Raise if this widget is folded away, so its membership cannot change.

    Moving a widget into or out of a closed group would be half of the trade
    folding makes: it would vanish from the board with nothing taking its place,
    or appear on it with nothing having made way.
    """
    if item.parent_id in _shut(items):
        raise NoRoomError(
            f"Not regrouped: {item.id} is inside folded group {item.parent_id}. Unfold that first."
        )


def gather(group: ItemRead, items: list[ItemRead]) -> list[ItemRead]:
    """Put these widgets in this group, and return them as they now stand."""
    if not is_group(group):
        raise NotAGroupError(group)
    if not group.payload.open:
        raise NoRoomError(f"Not grouped: {group.id} is folded. Unfold it, then put things in it.")
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

    Losing a container never silently takes its contents with it, so a folded
    group can only be removed while there is still room for what is inside it.
    """
    if not is_group(group):
        raise NotAGroupError(group)
    if not group.payload.open:
        unfold(group)
    repo.remove(group.id)
