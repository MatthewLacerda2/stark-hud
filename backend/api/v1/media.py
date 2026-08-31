"""Serve the local files that image and video items point at.

The item id is the handle, not the path: a filesystem path never appears in a
URL, and an item that points at a file which has since moved simply 404s. The
frontend turns that 404 into a visible placeholder rather than a broken tile.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from repositories import board as repo

router = APIRouter(prefix="/media", tags=["media"])

_MEDIA_KINDS = {"image", "video"}


@router.get("/{item_id}")
async def get_media(item_id: str) -> FileResponse:
    """Stream the file behind an image or video item."""
    item = repo.get(item_id)
    if item is None or item.payload.kind not in _MEDIA_KINDS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No media for that id")

    path = Path(item.payload.path)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File is gone: {path}",
        )
    return FileResponse(path)
