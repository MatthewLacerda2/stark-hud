"""Board endpoints. Every mutation is broadcast to connected clients."""

from fastapi import APIRouter, HTTPException, status

from core.hub import hub
from repositories import board as repo
from schemas.board import (
    Arrangement,
    Background,
    BoardStatus,
    Ink,
    ItemCreate,
    ItemRead,
    ItemUpdate,
    PlaybackReport,
)
from services import arrange as arrange_service
from services import board as service
from services import media as media_service

router = APIRouter(prefix="/board", tags=["board"])


def _get_or_404(item_id: str) -> ItemRead:
    """Load an item or raise 404."""
    item = repo.get(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.get("/items", response_model=list[ItemRead])
async def list_items() -> list[ItemRead]:
    """Return every item on the board, oldest first."""
    return repo.list_items()


@router.get("/status", response_model=BoardStatus)
async def board_status() -> BoardStatus:
    """Return what the board is carrying and the largest free rectangle."""
    return service.status()


@router.get("/background", response_model=Background | None)
async def get_background() -> Background | None:
    """Return the current video background, or null for the plain dark ground."""
    return repo.get_background()


@router.put("/background", response_model=Background)
async def set_background(payload: Background) -> Background:
    """Set the looping video behind the board. Always silent."""
    background = service.set_background(payload)
    await hub.broadcast("background.changed", payload.model_dump(mode="json"))
    assert background is not None
    return background


@router.delete("/background", status_code=status.HTTP_204_NO_CONTENT)
async def clear_background() -> None:
    """Go back to the plain dark ground."""
    service.set_background(None)
    await hub.broadcast("background.changed", None)


@router.get("/ink", response_model=Ink | None)
async def get_ink() -> Ink | None:
    """Return the board's default text colour, or null for the stylesheet's."""
    return repo.get_ink()


@router.put("/ink", response_model=Ink)
async def set_ink(payload: Ink) -> Ink:
    """Set the colour every widget writes in unless it was given one of its own."""
    ink = service.set_ink(payload)
    await hub.broadcast("ink.changed", payload.model_dump(mode="json"))
    assert ink is not None
    return ink


@router.delete("/ink", status_code=status.HTTP_204_NO_CONTENT)
async def clear_ink() -> None:
    """Go back to the board's own ink, which is white at 65%."""
    service.set_ink(None)
    await hub.broadcast("ink.changed", None)


@router.post("/items", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate) -> ItemRead:
    """Add an item, auto-placing it when coordinates are omitted."""
    item = service.create(payload)
    await hub.broadcast("item.created", item.model_dump(mode="json"))
    return item


@router.put("/items/by-key/{key}", response_model=ItemRead)
async def upsert_by_key(key: str, payload: ItemCreate) -> ItemRead:
    """Write the panel called ``key``, creating it the first time.

    For anything that refreshes: the caller names its panel and never has to
    remember an id, so losing local state — or being restarted, or replaced by a
    different process — costs nothing.

    Position is honoured on the first write and ignored afterwards. A refresher
    sends the same body every time, and if that moved the widget, dragging one
    would be undone by the next update seconds later.

    Only the payload is rewritten, so the item's own fields — its description
    among them — outlive every refresh. That is the whole reason a note about a
    panel is kept on the item and not inside what the panel is showing.
    """
    existing = repo.get_by_key(key)
    if existing is None:
        item = service.create(payload.model_copy(update={"key": key}))
        await hub.broadcast("item.created", item.model_dump(mode="json"))
        return item

    item = service.update(existing, ItemUpdate(payload=payload.payload))
    await hub.broadcast("item.updated", item.model_dump(mode="json"))
    return item


@router.patch("/items/{item_id}", response_model=ItemRead)
async def update_item(item_id: str, payload: ItemUpdate) -> ItemRead:
    """Apply a partial update to an item."""
    item = service.update(_get_or_404(item_id), payload)
    await hub.broadcast("item.updated", item.model_dump(mode="json"))
    return item


@router.post("/arrange", response_model=list[ItemRead])
async def arrange(payload: Arrangement) -> list[ItemRead]:
    """Apply several changes as one, judged by the arrangement they produce.

    A swap is the case this exists for: two widgets of the same size trade
    places, which is illegal at every moment in between and perfectly legal at
    the end. On a full board there is nowhere to park one of them, so without
    this the swap is not slow, it is impossible.

    Atomic — a rejected batch changes nothing — and broadcast as one event
    carrying the whole board, because ten `item.updated` would make a
    simultaneous rearrangement crawl across the television one widget at a time.
    """
    items = arrange_service.rearrange(payload.changes)
    await hub.broadcast("board.arranged", {"items": [i.model_dump(mode="json") for i in items]})
    return items


@router.post("/items/{item_id}/playback", response_model=ItemRead)
async def report_playback(item_id: str, payload: PlaybackReport) -> ItemRead:
    """Record what the browser says a media widget is doing.

    The only route on this board that runs the other way. Everything else is
    written by whoever drives the board and drawn by the TV; a file that is gone,
    or in a codec the browser refuses, is a thing only the TV can find out — and
    without somewhere to say it, it would be visible from the sofa and nowhere
    else.

    It lands on the item rather than in the payload, so a widget rewritten by its
    owner keeps it. A finished track is also how the queue moves on: the rule for
    what follows the last one lives in the service, not in the page.
    """
    item = _get_or_404(item_id)
    if item.payload.kind != "media":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} is a {item.payload.kind}, which plays nothing",
        )
    item = media_service.report(item, payload)
    await hub.broadcast("item.updated", item.model_dump(mode="json"))
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(item_id: str) -> None:
    """Delete an item. A group's widgets are put back on the board, never deleted."""
    service.remove(_get_or_404(item_id))
    await hub.broadcast("item.removed", {"id": item_id})


@router.delete("/items", response_model=dict[str, int])
async def clear_board() -> dict[str, int]:
    """Remove every item."""
    removed = repo.clear()
    await hub.broadcast("board.cleared", {"removed": removed})
    return {"removed": removed}
