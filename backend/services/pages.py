"""Pages: the board holds several and shows one.

A **page** is a whole board — the widgets, where they sit, the groups they fold
into. Every widget is on exactly one, named by the ``page`` field it carries,
and the board is turned to one of them at a time. So turning the page is a
single change to a single string, and nothing has to be gathered first: the bag
already exists, because the page a widget is on is part of the widget.

A page that is not showing takes no room and is not drawn. It is not asleep:
its panels go on taking writes by ``key`` the whole time, so the page you turn
back to is already current rather than rebuilt. That is what makes a page change
a cut on the television instead of a reload.

Placement, collision and ``board_status`` are all judged against one page, which
is why each page has the whole grid to itself. Turning to a page nobody has used
yet simply shows an empty board — that is how a new page is started, and why
there is nothing to create.

A **group** is the smaller thing and stays the smaller thing: a handful of
widgets on one page that fold into a shelf together. A group and its widgets
are always on the same page and move between pages as one.
"""

from core.config import get_settings
from core.refusal import BoardRefusal
from repositories import board as repo
from schemas.board import DEFAULT_PAGE, ItemRead
from services import events, groups
from services.placement import NoRoomError, illegal

__all__ = [
    "DEFAULT_PAGE",
    "GroupSplitError",
    "NoRoomError",
    "drawn",
    "named",
    "names",
    "on",
    "send",
    "show",
    "showing",
]


class GroupSplitError(BoardRefusal):
    """Raised when a widget is sent to another page without the group holding it.

    A group and what it holds are one thing on one page. Left behind, the group
    would fold into a shelf on a board its widgets are not on; sent on alone,
    the widget would reappear the next time somebody unfolded a group two pages
    away. Name the group instead and its widgets travel with it.
    """

    def __init__(self, item: ItemRead) -> None:
        self.item = item
        super().__init__(
            f"{item.id} is inside group {item.parent_id}, and a group is on one page. "
            f"Send {item.parent_id} instead and its widgets go with it."
        )


def _grid() -> tuple[int, int]:
    """Return the configured (cols, rows)."""
    settings = get_settings()
    return settings.GRID_COLS, settings.GRID_ROWS


def named(page: str | None) -> str:
    """The page a caller means. No name at all means the one the board starts on.

    Spelled this way rather than refused because the common case is coming back:
    a session that has turned the board to something and wants the ordinary
    board again should not have to remember what it is called.
    """
    return (page or "").strip() or DEFAULT_PAGE


def showing() -> str:
    """Which page the board is turned to."""
    return repo.showing()


def on(items: list[ItemRead], page: str | None = None) -> list[ItemRead]:
    """The widgets on one page, which is the showing one unless you say."""
    wanted = page if page is not None else repo.showing()
    return [i for i in items if i.page == wanted]


def drawn(items: list[ItemRead], page: str | None = None) -> list[ItemRead]:
    """The widgets actually taking up room, out of everything that exists.

    Two rules, in this order: a widget on another page is not here at all, and
    of what is left, an open group takes up nothing while a folded one takes the
    place of what it holds. Everything that asks "will this fit" asks it here,
    so the two rules are never applied in one place and forgotten in another.
    """
    return groups.on_board(on(items, page))


def names(items: list[ItemRead]) -> list[str]:
    """Every page this board carries, in order.

    A page is nothing but a name its widgets hold, so a page with nothing on it
    would otherwise vanish the moment you turned away from it. The two that are
    always listed are the one being shown and the one the board starts on.
    """
    return sorted({DEFAULT_PAGE, repo.showing(), *(i.page for i in items)})


async def show(page: str) -> list[ItemRead]:
    """Turn the board to a page, and return it whole.

    Nothing is validated and nothing moves: a page keeps its own layout, which
    was legal when it was built and is legal now, and no widget is touched by
    the turn. What changes is one name — which is exactly why this is one call
    and could not be several.

    The board comes back whole because the one event this sends carries it
    whole, and the television cuts rather than dealing widgets out one by one.
    """
    repo.set_showing(named(page))
    board = repo.list_items()
    await events.arranged(board)
    return board


def _whole(items: list[ItemRead]) -> list[ItemRead]:
    """These widgets, plus whatever any group among them is holding.

    Kept in the order they were named, one each: naming a group and one of its
    widgets is a caller saying the same thing twice, not a widget to move twice.
    """
    going: dict[str, ItemRead] = {}
    for item in items:
        if item.parent_id is not None and not groups.is_group(item):
            raise GroupSplitError(item)
        going[item.id] = item
        if groups.is_group(item):
            going.update({held.id: held for held in groups.members(item)})
    return list(going.values())


async def send(items: list[ItemRead], page: str) -> list[ItemRead]:
    """Move these widgets to another page, keeping their size and their place.

    Refused, whole, when they would not fit where they are going — nothing is
    shoved aside here either, and half a screen arriving is worse than none of
    it. The answer is the same as everywhere else on this board: make room on
    the far page with ``arrange``, then send.
    """
    name = named(page)
    going = {i.id: i.model_copy(update={"page": name}) for i in _whole(items)}
    proposed = [going.get(i.id, i) for i in repo.list_items()]

    why = illegal(drawn(proposed, name), *_grid())
    if why is not None:
        raise NoRoomError(f"Not sent to {name!r}: {why}")
    settled = [i for i in repo.swap(proposed) if i.id in going]
    # The whole board again: widgets have left the page that is showing, or
    # arrived on it, and either way several of them moved at once.
    await events.arranged()
    return settled
