"""Grid placement: default sizes, free-slot search, occupancy reporting.

The board is a fixed grid and never scrolls, so space is finite and running out
is a normal outcome. Nothing here silently shrinks or evicts an item: when a
request does not fit, the caller is told what is free and decides what to do.
"""

from schemas.board import ItemRead, Payload, Placement

# Sizes tuned for a 1080p TV read from a sofa, not for desktop density.
_DEFAULT_SIZES: dict[str, tuple[int, int]] = {
    "note": (3, 2),
    "text": (3, 1),
    "box": (4, 3),
    "image": (3, 3),
    "video": (6, 4),
    "chart": (4, 3),
    "notification": (3, 1),
}


class BoardFullError(Exception):
    """Raised when no free rectangle of the requested size exists."""

    def __init__(self, w: int, h: int, cells_free: int) -> None:
        self.w = w
        self.h = h
        self.cells_free = cells_free
        detail = (
            "board is full"
            if cells_free == 0
            else f"{cells_free} cells free, but none form a {w}x{h} rectangle"
        )
        super().__init__(f"No free {w}x{h} slot: {detail}")


def default_size(payload: Payload) -> tuple[int, int]:
    """Return the default (w, h) for an item kind."""
    return _DEFAULT_SIZES.get(payload.kind, (3, 2))


def _occupancy(items: list[ItemRead], cols: int, rows: int) -> list[list[bool]]:
    """Mark every cell covered by an existing item."""
    grid = [[False] * cols for _ in range(rows)]
    for item in items:
        for row in range(item.y, min(item.y + item.h, rows)):
            for col in range(item.x, min(item.x + item.w, cols)):
                grid[row][col] = True
    return grid


def _fits(grid: list[list[bool]], x: int, y: int, w: int, h: int) -> bool:
    """Whether the w*h rectangle at (x, y) is entirely free."""
    return all(not grid[row][col] for row in range(y, y + h) for col in range(x, x + w))


def find_slot(items: list[ItemRead], w: int, h: int, cols: int, rows: int) -> Placement:
    """Return the first free slot for a w*h rectangle, scanning top-left first.

    Raises ``BoardFullError`` when nothing fits.
    """
    grid = _occupancy(items, cols, rows)
    for y in range(rows - h + 1):
        for x in range(cols - w + 1):
            if _fits(grid, x, y, w, h):
                return Placement(x=x, y=y, w=w, h=h)
    free = sum(1 for row in grid for cell in row if not cell)
    raise BoardFullError(w, h, free)


def is_free(
    items: list[ItemRead], place: Placement, cols: int, rows: int, ignore_id: str | None = None
) -> bool:
    """Whether an explicit placement is in bounds and unoccupied."""
    if place.x + place.w > cols or place.y + place.h > rows:
        return False
    others = [i for i in items if i.id != ignore_id]
    return _fits(_occupancy(others, cols, rows), place.x, place.y, place.w, place.h)


def largest_free_rect(items: list[ItemRead], cols: int, rows: int) -> Placement | None:
    """Return the biggest free rectangle by area, or ``None`` when full.

    Brute force over a 12x8 grid is a few thousand checks — cheap, and it keeps
    the answer exact so a caller can trust it before choosing a size.
    """
    grid = _occupancy(items, cols, rows)
    best: Placement | None = None
    for y in range(rows):
        for x in range(cols):
            if grid[y][x]:
                continue
            for h in range(1, rows - y + 1):
                for w in range(1, cols - x + 1):
                    if not _fits(grid, x, y, w, h):
                        continue
                    if best is None or w * h > best.w * best.h:
                        best = Placement(x=x, y=y, w=w, h=h)
    return best
