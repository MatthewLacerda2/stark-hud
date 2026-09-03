"""Placement: default sizes, free-slot search, occupancy reporting.

The board is a fixed space and never scrolls, so room is finite and running out
is a normal outcome. Nothing here silently shrinks or evicts an item: when a
request does not fit, the caller is told what is free and decides what to do.

Coordinates are fractional, so there is no lattice of slots to walk and there
are infinitely many places a widget could sit. What keeps that tractable is
that a widget which may not overlap always comes to rest flush against another
widget's edge or against a wall — stopping a hair short of one never gains
anything. So the only positions worth testing are the edges already on the
board, and every question below is answered by walking that short list.
"""

from collections.abc import Iterator
from itertools import combinations

from schemas.board import MIN_SIZE, ItemRead, Payload, Placement

# Sizes tuned for a 1080p TV read from a sofa, not for desktop density. On the
# 32x18 grid a cell is roughly 60x60px, so these are deliberately generous.
_DEFAULT_SIZES: dict[str, tuple[float, float]] = {
    "note": (8, 4),
    "text": (8, 3),
    "list": (7, 7),
    "box": (10, 6),
    "image": (8, 6),
    "video": (16, 9),
    # Wide enough for a title beside the art and tall enough to be a player
    # rather than a thumbnail — comfortably over the four cells below which it
    # stops drawing one.
    "media": (10, 6),
    "chart": (10, 7),
    "inbox": (8, 8),
    # Three rows so the date shows by default; squash it to two for time only.
    "clock": (7, 4),
    # Tall like the inbox: a feed nobody scrolls is only as useful as the number
    # of lines it can show at once.
    "feed": (9, 10),
    # A folded group is a shelf of three icons and a blurred fourth. It says
    # what kind of things are inside and that there are several, which is all it
    # ever says — so it is the same small size holding five or twenty.
    "group": (4, 3),
}

# Two edges that ought to meet arrive as sums of decimals, and 0.1 + 0.2 is not
# 0.3. Anything closer together than this is the same edge, not an overlap.
_EPS = 1e-9


class BoardFullError(Exception):
    """Raised when no free rectangle of the requested size exists."""

    def __init__(self, w: float, h: float, cells_free: float) -> None:
        self.w = w
        self.h = h
        self.cells_free = cells_free
        detail = (
            "board is full"
            if cells_free <= _EPS
            else f"{cells(cells_free)} cells free, but none form a {size(w, h)} rectangle"
        )
        super().__init__(f"No free {size(w, h)} slot: {detail}")


def cells(value: float) -> str:
    """A measurement the way somebody would say it: 7, not 7.0; 7.5 stays 7.5.

    Coordinates are floats now and almost all of them are whole, so every line
    a human or a model reads goes through this rather than advertising a board
    made of 32.0 columns.
    """
    return f"{value:g}"


def size(w: float, h: float) -> str:
    """A width and a height as one phrase: ``10x7``."""
    return f"{cells(w)}x{cells(h)}"


def default_size(payload: Payload) -> tuple[float, float]:
    """Return the default (w, h) for an item kind."""
    return _DEFAULT_SIZES.get(payload.kind, (8, 4))


def _spans_meet(a: float, a_len: float, b: float, b_len: float) -> bool:
    """Whether two runs along one axis share more than a rounding error."""
    return a + a_len > b + _EPS and b + b_len > a + _EPS


def _clear(items: list[ItemRead], x: float, y: float, w: float, h: float) -> bool:
    """Whether the rectangle at (x, y) touches none of these items."""
    return not any(_spans_meet(i.x, i.w, x, w) and _spans_meet(i.y, i.h, y, h) for i in items)


def _free_area(items: list[ItemRead], cols: int, rows: int) -> float:
    """How much of the board nothing is sitting on."""
    return max(0.0, cols * rows - sum(i.w * i.h for i in items))


def _candidates(edges: set[float], limit: float) -> list[float]:
    """The near wall and every edge, in reading order, that still leaves room."""
    return sorted(e for e in {0.0} | edges if e <= limit + _EPS)


def find_slot(items: list[ItemRead], w: float, h: float, cols: int, rows: int) -> Placement:
    """Return the first free slot for a w-by-h rectangle, scanning top-left first.

    A rectangle that fits anywhere also fits with its left edge against a wall
    or somebody's right edge, and its top against a wall or somebody's bottom:
    slide it left until it stops, then up until it stops. So the far edges are
    the whole search space — and because sliding only ever makes a position
    earlier in reading order, this returns the same top-left-most slot the old
    cell-by-cell scan did.

    Raises ``BoardFullError`` when nothing fits.
    """
    xs = _candidates({i.x + i.w for i in items}, cols - w)
    ys = _candidates({i.y + i.h for i in items}, rows - h)
    for y in ys:
        for x in xs:
            if _clear(items, x, y, w, h):
                return Placement(x=x, y=y, w=w, h=h)
    raise BoardFullError(w, h, _free_area(items, cols, rows))


def is_free(
    items: list[ItemRead], place: Placement, cols: int, rows: int, ignore_id: str | None = None
) -> bool:
    """Whether an explicit placement is in bounds and unoccupied."""
    if place.x + place.w > cols + _EPS or place.y + place.h > rows + _EPS:
        return False
    others = [i for i in items if i.id != ignore_id]
    return _clear(others, place.x, place.y, place.w, place.h)


def _gaps(blockers: list[tuple[float, float]], width: float) -> Iterator[tuple[float, float]]:
    """The free runs left across a band, as (x, w) pairs."""
    cursor = 0.0
    for left, right in sorted(blockers):
        if left > cursor:
            yield cursor, left - cursor
        cursor = max(cursor, right)
    if width > cursor:
        yield cursor, width - cursor


def largest_free_rect(items: list[ItemRead], cols: int, rows: int) -> Placement | None:
    """Return the biggest free rectangle by area, or ``None`` when nothing fits.

    Exact rather than approximate, so a caller can trust it before choosing a
    size. A free rectangle nothing can be grown past is bounded on all four
    sides, so its top is a wall or somebody's bottom edge and its bottom is a
    wall or somebody's top edge. Take each of those bands in turn, sweep the
    widgets crossing it, and the gaps between them are the widest that band has
    to offer.
    """
    tops = sorted({0.0} | {i.y + i.h for i in items})
    bottoms = sorted({float(rows)} | {i.y for i in items})
    best: Placement | None = None
    for top in tops:
        for bottom in bottoms:
            h = bottom - top
            if h < MIN_SIZE:
                continue
            crossing = [(i.x, i.x + i.w) for i in items if _spans_meet(i.y, i.h, top, h)]
            for x, w in _gaps(crossing, cols):
                if w >= MIN_SIZE and (best is None or w * h > best.w * best.h):
                    best = Placement(x=x, y=top, w=w, h=h)
    return best


def overlapping(items: list[ItemRead]) -> tuple[ItemRead, ItemRead] | None:
    """The first two widgets in an arrangement that cannot both be where they say.

    Asked of a whole arrangement rather than of one placement, because some
    changes are only legal as a set: folding a group takes several widgets off
    the board and puts one in their place, and no step of that on its own is a
    legal board. What has to be true is the arrangement it produces.
    """
    for a, b in combinations(items, 2):
        if _spans_meet(a.x, a.w, b.x, b.w) and _spans_meet(a.y, a.h, b.y, b.h):
            return a, b
    return None


def outside(items: list[ItemRead], cols: int, rows: int) -> ItemRead | None:
    """The first widget in an arrangement that hangs off the board."""
    return next(
        (i for i in items if i.x + i.w > cols + _EPS or i.y + i.h > rows + _EPS),
        None,
    )
