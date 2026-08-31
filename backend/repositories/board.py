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

from schemas.board import ItemRead, Payload

_items: dict[str, ItemRead] = {}


def list_items() -> list[ItemRead]:
    """Return every item, oldest first."""
    return sorted(_items.values(), key=lambda i: i.created_at)


def get(item_id: str) -> ItemRead | None:
    """Return one item or ``None``."""
    return _items.get(item_id)


def add(
    payload: Payload, x: int, y: int, w: int, h: int, parent_id: str | None, pinned: bool
) -> ItemRead:
    """Insert a new item at an already-resolved position."""
    item = ItemRead(
        id=uuid.uuid4().hex[:12],
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
    """Remove every item. Returns how many were dropped."""
    count = len(_items)
    _items.clear()
    return count
