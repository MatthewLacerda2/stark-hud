"""Groups: folding a handful of widgets into one, and unfolding them again.

A group is a widget that holds widgets, and membership is ``parent_id`` on the
widgets themselves. Nothing is laid out inside a group and nothing moves into
one — the edge is the whole mechanism.

What a group has that no other widget has is two states, and what they do with
the room the group holds:

- **Open**, the group occupies nothing and its widgets are on the board exactly
  where they always were.
- **Folded**, its widgets come off the board and the group takes their place.

That trade is why each of these is a service rather than a field somebody sets.
Both halves have to happen at once or the board is briefly illegal, and either
half can be refused: a fold has to land somewhere free, and an unfold has to
find the room its widgets left still empty. Nothing is shoved aside to make
either work, which is the answer the board gives everywhere else.

A group is a handful of widgets on one page, not a page of its own. A whole
board's worth of layout is a page — see ``services.pages`` — and a group lives
on one, folds on one, and moves between them with its widgets. There was a
third state here once, ``away``, which was a group doing a page's job badly: it
could not hold the widgets that were in no group, so the ordinary board came
back in three calls with the television watching it assemble.

Everything here is judged against one page's worth of widgets, because that is
what a board is. The filtering is a comparison on ``item.page`` rather than a
call into ``services.pages``: that module reaches back into this one for what a
fold is doing with the room, and one of the two has to be the plain half.
"""

from core.config import get_settings
from core.refusal import BoardRefusal
from repositories import board as repo
from schemas.board import GroupPayload, GroupState, ItemRead, Payload, Placement
from services import events
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
    "joining",
    "members",
    "on_board",
    "scatter",
    "unfold",
    "weightless",
]


class NotAGroupError(BoardRefusal):
    """Raised when something that is not a group is asked to behave like one."""

    def __init__(self, item: ItemRead) -> None:
        self.item = item
        super().__init__(f"{item.id} is a {item.payload.kind}, not a group")


class NestedGroupError(BoardRefusal):
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


def _folded(items: list[ItemRead]) -> set[str]:
    """The ids of the groups that are closed.

    One set answers both halves of the trade, which is what having two states
    rather than three buys: a folded group is exactly the one that is drawn,
    and exactly the one whose widgets are not.
    """
    return {i.id for i in items if (held := _as_group(i)) is not None and held.state == "folded"}


def on_board(items: list[ItemRead]) -> list[ItemRead]:
    """The widgets actually taking up room, out of one page's worth of them.

    An open group is a bracket rather than a pane, so it takes up nothing and
    its widgets take up what they always did. A folded group is the other way
    round. Everything not in a group is simply on the board.

    Callers pass the page they mean; ``services.pages.drawn`` is the two rules
    together and is what the rest of the backend actually calls.
    """
    folded = _folded(items)
    return [i for i in items if i.parent_id not in folded and (not is_group(i) or i.id in folded)]


def weightless(payload: Payload, parent_id: str | None, items: list[ItemRead]) -> bool:
    """Whether a widget of this description takes up no room at all.

    Two things do not: a group that is open, and anything inside a group that is
    folded. Neither can collide with anything, so neither has a slot found for
    it or its coordinates checked — a put-away widget's position is a note of
    where it comes back to, and the unfold is where that is finally tested.
    """
    if payload.kind == "group":
        return payload.state == "open"
    return parent_id in _folded(items)


def members(group: ItemRead, items: list[ItemRead] | None = None) -> list[ItemRead]:
    """The widgets inside a group, oldest first."""
    return [
        i for i in (items if items is not None else repo.list_items()) if i.parent_id == group.id
    ]


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
    """Fold or unfold, but only if the arrangement it produces is a legal board.

    Legal on the group's own page, which is the only board this can disturb: a
    group folds where its widgets are, and they are all on that page with it.
    """
    if not is_group(group):
        raise NotAGroupError(group)
    changed: dict[str, object] = {"payload": group.payload.model_copy(update={"state": state})}
    if place is not None:
        changed |= {"x": place.x, "y": place.y, "w": place.w, "h": place.h}
    turned = group.model_copy(update=changed)

    board = [turned if i.id == group.id else i for i in repo.list_items()]
    why = illegal(on_board([i for i in board if i.page == group.page]), *_grid())
    if why is not None:
        raise NoRoomError(f"Not {'unfolded' if state == 'open' else 'folded'}: {why}")
    return repo.replace(turned)


async def fold(group: ItemRead) -> ItemRead:
    """Close a group: its widgets come off the board and it takes their place.

    One event carrying the whole board, like every change here that moves more
    than one widget: a fold takes several off the board at once, and the
    television has to see that as one change or the fold crawls across the
    screen a widget at a time.
    """
    if not is_group(group):
        raise NotAGroupError(group)
    shut = _turn(group, "folded", _where_it_folds(group, members(group)))
    await events.arranged()
    return shut


async def unfold(group: ItemRead) -> ItemRead:
    """Open a group: it gives its room back and its widgets return to theirs."""
    opened = _turn(group, "open")
    await events.arranged()
    return opened


def _open_enough(item: ItemRead, items: list[ItemRead]) -> None:
    """Raise if this widget is off the board, so its membership cannot change.

    Moving a widget into or out of a group that is folded would be half of the
    trade folding makes: it would vanish from the board with nothing taking its
    place, or appear on it with nothing having made way. Membership changes
    while a group is open, which is also the only time anybody can see what
    they did.
    """
    if item.parent_id in _folded(items):
        raise NoRoomError(
            f"Not regrouped: {item.id} is inside {item.parent_id}, which is folded. "
            f"Unfold that group first."
        )


def joining(parent_id: str) -> ItemRead:
    """The group a widget is about to be put into, or a refusal saying why not.

    The one check ``create`` makes that ``gather`` also makes, because a widget
    created straight into a group never passes through ``gather`` at all — and a
    ``parent_id`` pointing at a note, or at a group on another page, is a widget
    nothing will ever draw.
    """
    parent = repo.get(parent_id)
    if parent is None:
        raise NoRoomError(f"No item {parent_id} to put this in.")
    held = _as_group(parent)
    if held is None:
        raise NotAGroupError(parent)
    if held.state != "open":
        raise NoRoomError(f"Not grouped: {parent_id} is folded, not open. Unfold it first.")
    return parent


async def gather(group: ItemRead, items: list[ItemRead]) -> list[ItemRead]:
    """Put these widgets in this group, and return them as they now stand.

    Everything joins the group's page as it joins the group: a group and its
    widgets are one thing on one board.
    """
    held = _as_group(group)
    if held is None:
        raise NotAGroupError(group)
    if held.state != "open":
        raise NoRoomError(
            f"Not grouped: {group.id} is folded, not open. Unfold it, then put things in it."
        )
    everything = repo.list_items()
    for item in items:
        if is_group(item):
            raise NestedGroupError(item)
        _open_enough(item, everything)
    joined = [i.model_copy(update={"parent_id": group.id, "page": group.page}) for i in items]
    # Grouping moves nothing when everything is already on the group's page,
    # which is the ordinary case and passes this without doing anything. A
    # widget arriving from another page does move, though — onto a board that
    # may already have something where it thinks it is — so the arrangement is
    # checked, the same as a fold is.
    board = {i.id: i for i in repo.list_items()} | {i.id: i for i in joined}
    why = illegal(on_board([i for i in board.values() if i.page == group.page]), *_grid())
    if why is not None:
        raise NoRoomError(f"Not grouped: {why}")
    held_now = [repo.replace(i) for i in joined]
    await events.arranged()
    return held_now


async def scatter(items: list[ItemRead]) -> list[ItemRead]:
    """Take these widgets out of whatever group they are in."""
    everything = repo.list_items()
    for item in items:
        _open_enough(item, everything)
    loose = [repo.replace(i.model_copy(update={"parent_id": None})) for i in items]
    await events.arranged()
    return loose


def disband(group: ItemRead) -> None:
    """Remove a group, putting its widgets back on the board first.

    Losing a container never silently takes its contents with it, so a group
    that is folded can only be removed while there is still room for what is
    inside it.

    Says nothing itself: ``services.board.remove`` is the only caller and sends
    one ``board.arranged`` once the group and its widgets have both settled,
    rather than an unfold's event and then a removal's.
    """
    held = _as_group(group)
    if held is None:
        raise NotAGroupError(group)
    if held.state != "open":
        _turn(group, "open")
    repo.remove(group.id)
