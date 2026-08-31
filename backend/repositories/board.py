"""Board state. The only module that touches the store.

There is no database in this phase: the board is a dict that dies with the
process. The repository boundary is kept anyway — every item is a serializable
Pydantic model, so persisting to a ``.hudtv`` file later means rewriting this
module and nothing else.

Handlers are async but these functions are not: there is no I/O to await, and
the event loop is single-threaded, so a call that does not await is atomic.
"""

import uuid
from datetime import UTC, datetime

from schemas.board import Background, ItemRead, Payload

_items: dict[str, ItemRead] = {}
_background: Background | None = None


def list_items() -> list[ItemRead]:
    """Return every item, oldest first."""
    return sorted(_items.values(), key=lambda i: i.created_at)


def get(item_id: str) -> ItemRead | None:
    """Return one item or ``None``."""
    return _items.get(item_id)


def get_by_key(key: str) -> ItemRead | None:
    """Return the item carrying ``key``, or ``None``.

    Keys are how a repeating writer finds its own panel again. They are unique
    by convention, not by constraint; the first match wins.
    """
    return next((item for item in list_items() if item.key == key), None)


def add(
    payload: Payload,
    x: int,
    y: int,
    w: int,
    h: int,
    parent_id: str | None,
    pinned: bool,
    key: str | None = None,
    opacity: float | None = None,
) -> ItemRead:
    """Insert a new item at an already-resolved position."""
    item = ItemRead(
        id=uuid.uuid4().hex[:12],
        key=key,
        opacity=opacity,
        payload=payload,
        x=x,
        y=y,
        w=w,
        h=h,
        parent_id=parent_id,
        pinned=pinned,
        created_at=datetime.now(UTC),
    )
    _items[item.id] = item
    return item


def replace(item: ItemRead) -> ItemRead:
    """Overwrite an existing item with an updated copy."""
    _items[item.id] = item
    return item


def remove(item_id: str) -> bool:
    """Delete an item. Returns whether it existed.

    Children of a removed box are orphaned, not deleted: losing a container
    should never silently take content with it.
    """
    if item_id not in _items:
        return False
    del _items[item_id]
    for child in list(_items.values()):
        if child.parent_id == item_id:
            _items[child.id] = child.model_copy(update={"parent_id": None})
    return True


def clear() -> int:
    """Remove every item. Returns how many were dropped.

    The background is not an item and survives: clearing the board is about what
    is on it, not what is behind it.
    """
    count = len(_items)
    _items.clear()
    return count


def get_background() -> Background | None:
    """Return the current video background, if any."""
    return _background


def set_background(background: Background | None) -> Background | None:
    """Replace the background. ``None`` falls back to the plain dark ground."""
    global _background  # noqa: PLW0603 - module-level store, same as _items
    _background = background
    return _background
