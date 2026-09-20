"""Rearranging the board: several changes as one, judged by what they produce.

Swapping two widgets of the same size took three calls — park A somewhere else,
move B into A's place, move A into B's — and the middle step was a lie: A was
put somewhere it did not belong purely so the board stayed legal on the way
past. On a full board there is nowhere to park it, so the swap was not slow, it
was impossible.

The cause is that "no overlap" was checked on every operation, while somebody
asking for a rearrangement is describing an end state. So the rule here is:

    **A batch is legal if the arrangement it produces is legal**, whether or not
    any step along the way would have been.

One flat list, not a list of lists. Once the final state is what gets validated,
phases have nothing left to do — "shrink these, then move those" and "here is
the arrangement I want" become the same request.

Atomic. A rejected batch changes nothing: applying what fits would leave a
half-rearranged board on a television nobody is standing at.
"""

from core.config import get_settings
from core.refusal import BoardRefusal
from repositories import board as repo
from schemas.board import Change, ItemRead
from services import events, groups, pages
from services.placement import NoRoomError, UnfoldBlockedError, illegal


class UnknownTargetError(BoardRefusal):
    """Raised when a batch names a widget that is not there.

    A 404 rather than the usual 409: nothing about the board is in the way, the
    caller simply named something that is not on it.

    Named rather than skipped: a caller that meant to move four widgets and had
    one name wrong wants to know which, not to find three of them moved.
    """

    status = 404

    def __init__(self, target: str) -> None:
        self.target = target
        super().__init__(
            f"No item {target!r}. A batch changes nothing when one of its "
            f"targets is missing; call list_items to see what is there."
        )


class RepeatedTargetError(BoardRefusal):
    """Raised when a batch names one widget twice.

    Two entries for one widget is two answers to "where does this end up", and
    picking one of them silently is how a rearrangement does something nobody
    asked for. Since an entry is an end state, the fix is always to write one
    entry saying all of it.
    """

    def __init__(self, target: str) -> None:
        self.target = target
        super().__init__(
            f"{target!r} appears twice in this batch. An entry is where a widget "
            f"ends up, so say it once."
        )


def _changed(item: ItemRead, change: Change) -> ItemRead:
    """The widget as the batch asks for it. Anything left out is left alone.

    Every field but one is written straight onto the widget. ``folded`` is not
    a field a widget has — it is half of the trade folding makes, and the other
    half is the room its widgets give back — so it is applied afterwards, by
    ``services.groups``, once the rest of the batch has landed.
    """
    asked = change.model_dump(exclude={"target", "remove", "folded"}, exclude_none=True)
    return item.model_copy(update=asked)


def _targets(changes: list[Change]) -> dict[str, Change]:
    """Every change against the id of the widget it names, or raise saying why."""
    found: dict[str, Change] = {}
    for change in changes:
        item = repo.get(change.target) or repo.get_by_key(change.target)
        if item is None:
            raise UnknownTargetError(change.target)
        if item.id in found:
            raise RepeatedTargetError(change.target)
        found[item.id] = change
    return found


def _proposed(changes: dict[str, Change]) -> list[ItemRead]:
    """The board this batch would leave behind."""
    gone = {item_id for item_id, change in changes.items() if change.remove}
    kept = [
        _changed(item, changes[item.id]) if item.id in changes else item
        for item in repo.list_items()
        if item.id not in gone
    ]
    # A widget whose group was removed is orphaned rather than taken down with
    # it — the same rule the repository keeps — which is also why removing a
    # folded group can be refused: its widgets come back to the board here, and
    # the arrangement is judged with them on it.
    kept = [i.model_copy(update={"parent_id": None}) if i.parent_id in gone else i for i in kept]

    # Folding last, and against the board the rest of the batch produced: a
    # group folds where its widgets are, and this may be the batch that moved
    # them. A change that also names a place folds there instead — an entry
    # says where a widget ends up, and that one said.
    turning = {item_id: c for item_id, c in changes.items() if c.folded is not None}
    return [_folding(item, turning[item.id], kept) if item.id in turning else item for item in kept]


def _folding(group: ItemRead, change: Change, board: list[ItemRead]) -> ItemRead:
    """The group as this entry asks for it: closed, or open, on that board."""
    return groups.turned(
        group,
        "folded" if change.folded else "open",
        board,
        stays=change.x is not None or change.y is not None,
    )


def _opening(board: list[ItemRead], changes: dict[str, Change]) -> None:
    """Refuse an unfold in this batch by name, before the general judge speaks.

    ``illegal`` names the first two widgets in the same place, which is the
    right answer for a batch of moves and a thin one for a batch that asked a
    group to open: there the caller wants every blocker and the size of each
    overlap, because it is deciding between nudging one widget and telling the
    user the room is spoken for.
    """
    asked_open = [i for i in board if (c := changes.get(i.id)) is not None and c.folded is False]
    for group in asked_open:
        standing = groups.blocked(group, board)
        if standing:
            raise UnfoldBlockedError(group.id, standing)


async def rearrange(changes: list[Change]) -> list[ItemRead]:
    """Apply a batch as one transaction, and return the board it produced.

    Returned here specifically, where you most want to know what you got —
    rather than on every mutation, which would make every response larger for
    the many calls that do not care.

    One event, carrying the board whole: ten ``item.updated`` would render ten
    times and a simultaneous rearrangement would still crawl across the
    television a widget at a time.
    """
    settings = get_settings()
    asked = _targets(changes)
    board = _proposed(asked)
    _opening(board, asked)
    # Every page, not just the one showing. A batch may move a panel on a page
    # nobody is looking at, and that page has to be a board somebody could turn
    # back to — the bill for it arriving on the turn would be a refusal with
    # nothing on screen to explain it.
    for page in pages.names(board):
        why = illegal(pages.drawn(board, page), settings.GRID_COLS, settings.GRID_ROWS)
        if why is not None:
            raise NoRoomError(f"Not rearranged: {why}")
    settled = repo.swap(board)
    await events.arranged(settled)
    return settled
