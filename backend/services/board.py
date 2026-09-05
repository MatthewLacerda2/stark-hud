"""Board business logic: resolve placement, then mutate through the repository.

Handlers stay thin; the rules about where an item may land live here.
"""

from pathlib import Path

from core.config import get_settings
from repositories import board as repo
from schemas.board import (
    Background,
    BoardStatus,
    Ink,
    ItemCreate,
    ItemRead,
    ItemUpdate,
    Placement,
)
from services import groups
from services.placement import (
    cells,
    default_size,
    find_slot,
    is_free,
    largest_free_rect,
    size,
)


class SlotTakenError(Exception):
    """Raised when an explicit placement is out of bounds or already occupied."""

    def __init__(self, place: Placement) -> None:
        self.place = place
        super().__init__(
            f"Slot {size(place.w, place.h)} at ({cells(place.x)}, {cells(place.y)}) "
            f"is taken or out of bounds"
        )


class KeyTakenError(Exception):
    """Raised when a key is given to a second widget.

    A key names one widget. Two widgets holding one name made the second
    unreachable: every lookup — ``PUT /board/items/by-key``, ``wake_item``, the
    agent's panel writes every few seconds — took the first match, so the other
    one sat on the television being fed by nobody.

    The holder is named because a caller that hits this almost certainly wanted
    the panel path, which updates the widget already carrying the key instead of
    making a second one.
    """

    def __init__(self, key: str, holder: ItemRead) -> None:
        self.key = key
        self.holder = holder
        super().__init__(
            f"The key {key!r} already names {holder.payload.kind} {holder.id}. "
            f"Write to that widget instead — a key names one widget."
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


def set_ink(ink: Ink | None) -> Ink | None:
    """Set or clear the board's default text colour.

    Nothing to check that the colour type has not already checked, so this is a
    pass through — it is here so that setting the ink crosses the same boundary
    every other mutation crosses, rather than being the one that reaches past it.
    """
    return repo.set_ink(ink)


def icon_path(item: ItemRead, index: int | None = None) -> str | None:
    """The picture an icon points at, or ``None`` when it names a glyph.

    An icon is either a name from a closed set, which the browser draws itself,
    or a file on this machine, which only we can serve — and we serve it by the
    item's id, so the path never appears in a URL.

    Without an index this is the widget's own icon; with one it is that entry's,
    since a list carries an icon per line and they need telling apart.
    """
    if index is None:
        icon = getattr(item.payload, "icon", None)
    else:
        entries = getattr(item.payload, "items", [])
        entry = entries[index] if 0 <= index < len(entries) else None
        icon = getattr(entry, "icon", None)
    return icon if isinstance(icon, str) and icon.startswith("/") else None


def _grid() -> tuple[int, int]:
    """Return the configured (cols, rows)."""
    settings = get_settings()
    return settings.GRID_COLS, settings.GRID_ROWS


def _resolve(data: ItemCreate | ItemUpdate, current: ItemRead | None) -> Placement:
    """Work out where an item goes, honouring explicit coordinates when given.

    Only what is on the board is in the way, which is not everything that
    exists: an open group takes up no room and neither does anything folded
    inside a closed one. A widget that takes up no room has its coordinates
    recorded rather than checked — see ``groups.weightless``.
    """
    cols, rows = _grid()
    everything = repo.list_items()
    dw, dh = default_size(data.payload) if data.payload else (3.0, 2.0)

    w = data.w if data.w is not None else (current.w if current else dw)
    h = data.h if data.h is not None else (current.h if current else dh)
    x = data.x if data.x is not None else (current.x if current else None)
    y = data.y if data.y is not None else (current.y if current else None)

    payload = data.payload or (current.payload if current else None)
    parent_id = data.parent_id or (current.parent_id if current else None)
    if payload is not None and groups.weightless(payload, parent_id, everything):
        return Placement(x=x or 0.0, y=y or 0.0, w=w, h=h)

    items = groups.on_board(everything)
    if x is None or y is None:
        return find_slot(items, w, h, cols, rows)

    place = Placement(x=x, y=y, w=w, h=h)
    if not is_free(items, place, cols, rows, ignore_id=current.id if current else None):
        raise SlotTakenError(place)
    return place


def _claim(key: str | None, current: ItemRead | None) -> None:
    """Raise unless this key is free, or already this widget's own."""
    if key is None:
        return
    holder = repo.get_by_key(key)
    if holder is not None and (current is None or holder.id != current.id):
        raise KeyTakenError(key, holder)


def _described(data: ItemCreate | ItemUpdate, current: ItemRead | None) -> str | None:
    """The note an item is left with.

    Every field on an update treats ``None`` as "untouched", and this one does
    too — which leaves nothing meaning "take it off". An empty string is that: a
    note nobody wrote is the same as no note, so writing one erases it.
    """
    if data.description is None:
        return current.description if current else None
    return data.description.strip() or None


def create(data: ItemCreate) -> ItemRead:
    """Add an item, auto-placing it when coordinates are omitted."""
    _claim(data.key, None)
    place = _resolve(data, None)
    return repo.add(
        data.payload,
        place.x,
        place.y,
        place.w,
        place.h,
        data.parent_id,
        data.pinned,
        data.key,
        # These were accepted by the schema and then dropped here, so a widget
        # created with a colour came out with none until something updated it.
        opacity=data.opacity,
        color=data.color,
        background=data.background,
        border=data.border,
        scale=data.scale,
        description=_described(data, None),
    )


def update(item: ItemRead, data: ItemUpdate) -> ItemRead:
    """Apply a partial update, revalidating placement when geometry changes."""
    _claim(data.key, item)
    place = _resolve(data, item)
    return repo.replace(
        item.model_copy(
            update={
                "payload": data.payload if data.payload is not None else item.payload,
                "x": place.x,
                "y": place.y,
                "w": place.w,
                "h": place.h,
                "key": data.key if data.key is not None else item.key,
                "description": _described(data, item),
                "opacity": data.opacity if data.opacity is not None else item.opacity,
                "color": data.color if data.color is not None else item.color,
                "background": data.background if data.background is not None else item.background,
                "border": data.border if data.border is not None else item.border,
                "scale": data.scale if data.scale is not None else item.scale,
                "parent_id": data.parent_id if data.parent_id is not None else item.parent_id,
                "pinned": data.pinned if data.pinned is not None else item.pinned,
            }
        )
    )


def remove(item: ItemRead) -> None:
    """Delete a widget. A group gives its widgets back to the board first."""
    if groups.is_group(item):
        groups.disband(item)
        return
    repo.remove(item.id)


def status() -> BoardStatus:
    """Report what the board is carrying, so a caller can look before it leaps."""
    cols, rows = _grid()
    items = groups.on_board(repo.list_items())
    used = sum(i.w * i.h for i in items)
    total = cols * rows
    return BoardStatus(
        cols=cols,
        rows=rows,
        cells_total=total,
        cells_used=used,
        cells_free=total - used,
        item_count=len(items),
        largest_free_rect=largest_free_rect(items, cols, rows),
    )
