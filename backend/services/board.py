"""Board business logic: resolve placement, then mutate through the repository.

Handlers stay thin; the rules about where an item may land live here.
"""

from pathlib import Path

from core.config import get_settings
from repositories import board as repo
from schemas.board import Background, BoardStatus, ItemCreate, ItemRead, ItemUpdate, Placement
from services.placement import default_size, find_slot, is_free, largest_free_rect


class SlotTakenError(Exception):
    """Raised when an explicit placement is out of bounds or already occupied."""

    def __init__(self, place: Placement) -> None:
        self.place = place
        super().__init__(
            f"Slot {place.w}x{place.h} at ({place.x}, {place.y}) is taken or out of bounds"
        )


class MissingFileError(Exception):
    """Raised when a background points at a path that is not a file."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"No file at {path}")


def set_background(background: Background | None) -> Background | None:
    """Set or clear the video background, checking the file exists first.

    Items with a missing file show a visible placeholder, so the problem
    announces itself. A missing background is just darkness, indistinguishable
    from having set none — so this one is checked up front.
    """
    if background is not None and not Path(background.path).is_file():
        raise MissingFileError(background.path)
    return repo.set_background(background)


def _grid() -> tuple[int, int]:
    """Return the configured (cols, rows)."""
    settings = get_settings()
    return settings.GRID_COLS, settings.GRID_ROWS


def page_of(data: ItemCreate | ItemUpdate, current: ItemRead | None) -> int:
    """Which page an item belongs on: what was asked, what it had, or what shows."""
    if data.page is not None:
        return data.page
    return current.page if current else repo.get_page()


def _resolve(data: ItemCreate | ItemUpdate, current: ItemRead | None, page: int) -> Placement:
    """Work out where an item goes, honouring explicit coordinates when given.

    Only widgets on the same page are in the way. Each page is its own grid of
    the same size, so the same slot is free on one and taken on another.
    """
    cols, rows = _grid()
    items = [i for i in repo.list_items() if i.page == page]
    dw, dh = default_size(data.payload) if data.payload else (3, 2)

    base_w = current.w if current else dw
    base_h = current.h if current else dh
    w = data.w if data.w is not None else base_w
    h = data.h if data.h is not None else base_h

    x = data.x if data.x is not None else (current.x if current else None)
    y = data.y if data.y is not None else (current.y if current else None)

    if x is None or y is None:
        return find_slot(items, w, h, cols, rows)

    place = Placement(x=x, y=y, w=w, h=h)
    if not is_free(items, place, cols, rows, ignore_id=current.id if current else None):
        raise SlotTakenError(place)
    return place


def create(data: ItemCreate) -> ItemRead:
    """Add an item, auto-placing it when coordinates are omitted."""
    page = page_of(data, None)
    place = _resolve(data, None, page)
    return repo.add(
        data.payload,
        place.x,
        place.y,
        place.w,
        place.h,
        data.parent_id,
        data.pinned,
        data.key,
        page,
    )


def update(item: ItemRead, data: ItemUpdate) -> ItemRead:
    """Apply a partial update, revalidating placement when geometry changes."""
    page = page_of(data, item)
    place = _resolve(data, item, page)
    return repo.replace(
        item.model_copy(
            update={
                "payload": data.payload if data.payload is not None else item.payload,
                "page": page,
                "x": place.x,
                "y": place.y,
                "w": place.w,
                "h": place.h,
                "key": data.key if data.key is not None else item.key,
                "opacity": data.opacity if data.opacity is not None else item.opacity,
                "color": data.color if data.color is not None else item.color,
                "scale": data.scale if data.scale is not None else item.scale,
                "parent_id": data.parent_id if data.parent_id is not None else item.parent_id,
                "pinned": data.pinned if data.pinned is not None else item.pinned,
            }
        )
    )


def page_count() -> int:
    """How many pages exist: as many as the furthest one with anything on it."""
    return max((i.page for i in repo.list_items()), default=0) + 1


def status() -> BoardStatus:
    """Report occupancy of the page being shown, so a caller can look first."""
    cols, rows = _grid()
    page = repo.get_page()
    items = [i for i in repo.list_items() if i.page == page]
    used = sum(i.w * i.h for i in items)
    total = cols * rows
    return BoardStatus(
        cols=cols,
        rows=rows,
        page=page,
        pages=page_count(),
        cells_total=total,
        cells_used=used,
        cells_free=total - used,
        item_count=len(items),
        largest_free_rect=largest_free_rect(items, cols, rows),
    )
