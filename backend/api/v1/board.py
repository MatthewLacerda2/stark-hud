"""Board endpoints. Every mutation is broadcast to connected clients."""

from fastapi import APIRouter, HTTPException, status

from core.hub import hub
from repositories import board as repo
from schemas.board import BoardStatus, ItemCreate, ItemRead, ItemUpdate
from services import board as service

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
    """Return grid occupancy and the largest free rectangle."""
    return service.status()


@router.post("/items", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate) -> ItemRead:
    """Add an item, auto-placing it when coordinates are omitted."""
    item = service.create(payload)
    await hub.broadcast("item.created", item.model_dump(mode="json"))
    return item


@router.patch("/items/{item_id}", response_model=ItemRead)
async def update_item(item_id: str, payload: ItemUpdate) -> ItemRead:
    """Apply a partial update to an item."""
    item = service.update(_get_or_404(item_id), payload)
    await hub.broadcast("item.updated", item.model_dump(mode="json"))
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(item_id: str) -> None:
    """Delete an item. Children of a removed box are orphaned, not deleted."""
    _get_or_404(item_id)
    repo.remove(item_id)
    await hub.broadcast("item.removed", {"id": item_id})


@router.delete("/items", response_model=dict[str, int])
async def clear_board() -> dict[str, int]:
    """Remove every item."""
    removed = repo.clear()
    await hub.broadcast("board.cleared", {"removed": removed})
    return {"removed": removed}
