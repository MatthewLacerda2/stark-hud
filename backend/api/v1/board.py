"""Board endpoints.

Every mutation reaches the television, and none of it is announced from here:
the service that makes the change sends the event, so this router and the MCP
tools cannot disagree about what a write says and neither can forget to say it.
See ``services.events``.
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status

from repositories import board as repo
from schemas.board import (
    Arrangement,
    Background,
    BoardStatus,
    Ink,
    ItemCreate,
    ItemRead,
    ItemUpdate,
)
from services import arrange as arrange_service
from services import board as service
from services import origin


async def _telling(request: Request) -> AsyncIterator[None]:
    """Hold this request, as a line, for as long as it is being served.

    The seam on this side. A widget the agent writes over HTTP, or one a phone
    posts, gets an origin the same way an MCP call does — and it is attached
    here, once, for the whole router, rather than by each handler that happens
    to create something. The body is already read and cached by the time a
    dependency runs, so this costs a dictionary lookup.
    """
    body = await request.body()
    with origin.telling(origin.request(request.method, request.url.path, body)):
        yield


router = APIRouter(prefix="/board", tags=["board"], dependencies=[Depends(_telling)])


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
    background = await service.set_background(payload)
    assert background is not None
    return background


@router.delete("/background", status_code=status.HTTP_204_NO_CONTENT)
async def clear_background() -> None:
    """Go back to the plain dark ground."""
    await service.set_background(None)


@router.get("/ink", response_model=Ink | None)
async def get_ink() -> Ink | None:
    """Return the board's default text colour, or null for the stylesheet's."""
    return repo.get_ink()


@router.put("/ink", response_model=Ink)
async def set_ink(payload: Ink) -> Ink:
    """Set the colour every widget writes in unless it was given one of its own."""
    ink = await service.set_ink(payload)
    assert ink is not None
    return ink


@router.delete("/ink", status_code=status.HTTP_204_NO_CONTENT)
async def clear_ink() -> None:
    """Go back to the board's own ink, which is white at 65%."""
    await service.set_ink(None)


@router.post("/items", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate) -> ItemRead:
    """Add an item, auto-placing it when coordinates are omitted."""
    return await service.create(payload)


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
        return await service.create(payload.model_copy(update={"key": key}))
    return await service.update(existing, ItemUpdate(payload=payload.payload))


@router.patch("/items/{item_id}", response_model=ItemRead)
async def update_item(item_id: str, payload: ItemUpdate) -> ItemRead:
    """Apply a partial update to an item."""
    return await service.update(_get_or_404(item_id), payload)


@router.post("/arrange", response_model=list[ItemRead])
async def arrange(payload: Arrangement) -> list[ItemRead]:
    """Apply several changes as one, judged by the arrangement they produce.

    A swap is the case this exists for: two widgets of the same size trade
    places, which is illegal at every moment in between and perfectly legal at
    the end. On a full board there is nowhere to park one of them, so without
    this the swap is not slow, it is impossible.

    Atomic — a rejected batch changes nothing — and announced as one event
    carrying the whole board, because ten `item.updated` would make a
    simultaneous rearrangement crawl across the television one widget at a time.
    """
    return await arrange_service.rearrange(payload.changes)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(item_id: str) -> None:
    """Delete an item. A group's widgets are put back on the board, never deleted."""
    await service.remove(_get_or_404(item_id))


@router.delete("/items", response_model=dict[str, int])
async def clear_board() -> dict[str, int]:
    """Remove every item."""
    return {"removed": await service.clear()}
