"""Board business logic: resolve placement, mutate, and say so.

Handlers stay thin; the rules about where an item may land live here, and so
does telling the television what happened. Every function below that changes
anything is ``async`` for that one reason — the announcement is the awaited
thing — so a caller that writes through this cannot leave the TV showing the old
widget. See ``services.events``.
"""

from pathlib import Path

from core.config import get_settings
from core.refusal import BoardRefusal
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
from services import events, groups, pages, uploads
from services.placement import (
    cells,
    default_size,
    find_slot,
    is_free,
    largest_free_rect,
    size,
)


class SlotTakenError(BoardRefusal):
    """Raised when an explicit placement is out of bounds or already occupied."""

    def __init__(self, place: Placement) -> None:
        self.place = place
        super().__init__(
            f"Slot {size(place.w, place.h)} at ({cells(place.x)}, {cells(place.y)}) "
            f"is taken or out of bounds"
        )


class KeyTakenError(BoardRefusal):
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

    def extra(self) -> dict[str, object]:
        """The widget already holding the key, which is the one to write to."""
        return {"holder": self.holder.id}


class NotByPatchError(BoardRefusal):
    """Raised when an update tries to change what only a service may change.

    A group's state is half of a trade — its widgets come off the board and it
    takes their place — and a PATCH writing ``state`` straight through did the
    half that is a field and skipped the half that is a rule, leaving widgets
    stacked on the television. ``parent_id`` and ``page`` were the same hole and
    are simply not on ``ItemUpdate`` any more; this one has to be caught here,
    because a group's state arrives inside a payload that is otherwise ordinary.
    """

    def __init__(self, item: ItemRead) -> None:
        self.item = item
        super().__init__(
            f"{item.id} is a group, and a group is opened and closed by "
            f"fold_group and unfold_group, never by writing its state."
        )


class MissingFileError(BoardRefusal):
    """Raised when a background points at a path that is not a file."""

    status = 404

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"No file at {path}")


async def set_background(background: Background | None) -> Background | None:
    """Set or clear the video background, checking the file exists first.

    Items with a missing file show a visible placeholder, so the problem
    announces itself. A missing background is just darkness, indistinguishable
    from having set none — so this one is checked up front.
    """
    if background is not None and not Path(background.path).is_file():
        raise MissingFileError(background.path)
    stored = repo.set_background(background)
    await events.background_changed(stored)
    return stored


async def set_ink(ink: Ink | None) -> Ink | None:
    """Set or clear the board's default text colour.

    Nothing to check that the colour type has not already checked, so this is a
    pass through — it is here so that setting the ink crosses the same boundary
    every other mutation crosses, rather than being the one that reaches past it,
    and so that it announces itself like everything else.
    """
    stored = repo.set_ink(ink)
    await events.ink_changed(stored)
    return stored


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


def _resolve(data: ItemCreate | ItemUpdate, current: ItemRead | None, born: str = "") -> Placement:
    """Work out where an item goes, honouring explicit coordinates when given.

    Only what is on the board is in the way, which is not everything that
    exists: an open group takes up no room, neither does anything folded inside
    a closed one, and neither does a single widget on a page that is not this
    one. A widget that takes up no room has its coordinates recorded rather than
    checked — see ``groups.weightless``.

    The page judged against is the widget's own, never the one showing: a panel
    written every few seconds while its page is put away has to be measured
    against the board it will come back to. A widget that does not exist yet has
    no page of its own, so it is measured against the one it is being born on —
    which is ``born`` when its creator named one, and otherwise the one showing.
    """
    cols, rows = _grid()
    everything = repo.list_items()
    page = current.page if current else born or pages.showing()
    dw, dh = default_size(data.payload) if data.payload else (3.0, 2.0)

    w = data.w if data.w is not None else (current.w if current else dw)
    h = data.h if data.h is not None else (current.h if current else dh)
    x = data.x if data.x is not None else (current.x if current else None)
    y = data.y if data.y is not None else (current.y if current else None)

    payload = data.payload or (current.payload if current else None)
    # Only a creation says which group a widget joins. An update cannot — that
    # field is not on ``ItemUpdate`` — so for every other call the group it is
    # already in is the answer.
    parent_id = data.parent_id if isinstance(data, ItemCreate) else None
    if parent_id is None and current is not None:
        parent_id = current.parent_id
    if payload is not None and groups.weightless(payload, parent_id, everything):
        return Placement(x=x or 0.0, y=y or 0.0, w=w, h=h)

    items = pages.drawn(everything, page)
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


async def create(data: ItemCreate) -> ItemRead:
    """Add an item on the page it is born on, auto-placing it when asked to.

    Which page that is, in order: the group it is joining, since a group and its
    widgets are one thing on one board; then the page the creation named; then
    the page that is showing. The last of those is right for a session adding a
    widget to the board it is looking at, and it is exactly what a writer that
    cannot see the television must not be given — so such a writer names one.

    A widget created straight into a group never passes through ``gather``, so
    the one check that would have made is made here instead.

    The widget reaches the socket from here, with whatever made it — see
    ``services.events.created`` — so no route and none of the sixteen ``add_``
    tools has anything to remember.
    """
    _claim(data.key, None)
    parent = groups.joining(data.parent_id) if data.parent_id else None
    if parent is not None:
        born = parent.page
    else:
        born = pages.named(data.page) if data.page else ""
    place = _resolve(data, None, born)
    item = repo.add(
        data.payload,
        place.x,
        place.y,
        place.w,
        place.h,
        parent_id=data.parent_id,
        key=data.key,
        page=born or None,
        # These were accepted by the schema and then dropped here, so a widget
        # created with a colour came out with none until something updated it.
        color=data.color,
        border=data.border,
        scale=data.scale,
        description=_described(data, None),
    )
    await events.created(item)
    return item


async def update(item: ItemRead, data: ItemUpdate) -> ItemRead:
    """Apply a partial update, revalidating placement when geometry changes."""
    if data.payload is not None and groups.is_group(item):
        raise NotByPatchError(item)
    _claim(data.key, item)
    place = _resolve(data, item)
    written = repo.replace(
        item.model_copy(
            update={
                "payload": data.payload if data.payload is not None else item.payload,
                "x": place.x,
                "y": place.y,
                "w": place.w,
                "h": place.h,
                "key": data.key if data.key is not None else item.key,
                "description": _described(data, item),
                "color": data.color if data.color is not None else item.color,
                "border": data.border if data.border is not None else item.border,
                "scale": data.scale if data.scale is not None else item.scale,
            }
        )
    )
    await events.updated(written)
    return written


async def remove(item: ItemRead) -> None:
    """Delete a widget. A group gives its widgets back to the board first.

    A group goes out as ``board.arranged`` rather than ``item.removed``, because
    removing one is not one widget disappearing: it may unfold first, and its
    widgets are handed back to the board where they were. Sending only the
    group's id left the television drawing those widgets wherever it last saw
    them, which is the failure this whole module exists to stop.
    """
    if groups.is_group(item):
        groups.disband(item)
        await events.arranged()
        return
    repo.remove(item.id)
    await events.removed(item.id)
    # A queue that has just stopped existing is the moment an uploaded file may
    # have become disk used for nothing. Only files inside the upload directory
    # are ever candidates — `services.uploads.sweep` says why, and why it waits.
    uploads.sweep()


async def clear() -> int:
    """Take every widget off every page. Returns how many went.

    Here rather than in a handler so that the two surfaces empty the board the
    same way and neither is the one that reaches past the services to do it.
    """
    removed = repo.clear()
    await events.cleared(removed)
    uploads.sweep()
    return removed


def status() -> BoardStatus:
    """Report what the page that is showing is carrying, so a caller can look
    before it leaps.

    One page, because each page has the whole grid to itself. The pages the
    board is carrying are named here too: a board with three of them and a
    clock on this one would otherwise read as a board with one clock on it.
    """
    cols, rows = _grid()
    everything = repo.list_items()
    items = pages.drawn(everything)
    used = sum(i.w * i.h for i in items)
    total = cols * rows
    return BoardStatus(
        showing=pages.showing(),
        pages=pages.names(everything),
        cols=cols,
        rows=rows,
        cells_total=total,
        cells_used=used,
        cells_free=total - used,
        item_count=len(items),
        largest_free_rect=largest_free_rect(items, cols, rows),
    )
