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
from repositories import board as repo
from schemas.board import Change, ItemRead
from services import groups
from services.placement import NoRoomError, illegal


class UnknownTargetError(Exception):
    """Raised when a batch names a widget that is not there.

    Named rather than skipped: a caller that meant to move four widgets and had
    one name wrong wants to know which, not to find three of them moved.
    """

    def __init__(self, target: str) -> None:
        self.target = target
        super().__init__(
            f"No item {target!r}. A batch changes nothing when one of its "
            f"targets is missing; call list_items to see what is there."
        )


class RepeatedTargetError(Exception):
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
    """The widget as the batch asks for it. Anything left out is left alone."""
    asked = change.model_dump(exclude={"target", "remove"}, exclude_none=True)
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
    return [i.model_copy(update={"parent_id": None}) if i.parent_id in gone else i for i in kept]


def rearrange(changes: list[Change]) -> list[ItemRead]:
    """Apply a batch as one transaction, and return the board it produced.

    Returned here specifically, where you most want to know what you got —
    rather than on every mutation, which would make every response larger for
    the many calls that do not care.
    """
    settings = get_settings()
    board = _proposed(_targets(changes))
    why = illegal(groups.on_board(board), settings.GRID_COLS, settings.GRID_ROWS)
    if why is not None:
        raise NoRoomError(f"Not rearranged: {why}")
    return repo.swap(board)
