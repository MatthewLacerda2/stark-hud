"""Serve the local files that items point at: their media, and their icons.

The item id is the handle, not the path: a filesystem path never appears in a
URL, and an item that points at a file which has since moved simply 404s. The
frontend turns that 404 into a visible placeholder rather than a broken widget.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from repositories import board as repo
from services import board as service
from services import media as media_service

router = APIRouter(prefix="/media", tags=["media"])

_MEDIA_KINDS = {"image", "video"}


def _stream(path: str) -> FileResponse:
    """Send a file back, 404ing with its path when it is no longer there."""
    target = Path(path)
    if not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File is gone: {target}")
    return FileResponse(target)


@router.get("/background")
async def get_background_media() -> FileResponse:
    """Stream the video behind the grid."""
    background = repo.get_background()
    if background is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No background set")
    return _stream(background.path)


@router.get("/{item_id}")
async def get_media(item_id: str) -> FileResponse:
    """Stream the file behind an image or video item."""
    item = repo.get(item_id)
    if item is None or item.payload.kind not in _MEDIA_KINDS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No media for that id")
    return _stream(item.payload.path)


def _icon(item_id: str, index: int | None) -> FileResponse:
    """Send back the picture an icon points at, if that is what it is."""
    item = repo.get(item_id)
    path = service.icon_path(item, index) if item else None
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No icon image for that id"
        )
    return _stream(path)


@router.get("/{item_id}/track/{index}")
async def get_track(item_id: str, index: int) -> FileResponse:
    """Stream one track of a media widget's queue.

    Addressed by the widget's id and the track's place in the queue, for the
    same reason a picture is addressed by an item id: the path stays on the
    server. It is also what makes an album with an apostrophe and spaces in its
    directory name work without a thought — none of it is ever a URL.
    """
    item = repo.get(item_id)
    path = media_service.track_path(item, index) if item else None
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such track")
    return _stream(path)


@router.get("/{item_id}/track/{index}/art")
async def get_track_art(item_id: str, index: int) -> FileResponse:
    """Stream the album art beside a track, when the folder has one.

    A 404 here is ordinary, not an error: plenty of albums have no picture in
    the folder, and the widget draws a symbol instead.
    """
    item = repo.get(item_id)
    path = media_service.art_path(item, index) if item else None
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No art beside that track"
        )
    return _stream(path)


@router.get("/{item_id}/icon")
async def get_icon(item_id: str) -> FileResponse:
    """Stream the picture a widget's icon points at, when it is a path.

    The same route a notification's icon has, addressed the same way: an icon
    that names a glyph has nothing to serve and is a 404 here, because the
    browser draws that one itself.
    """
    return _icon(item_id, None)


@router.get("/{item_id}/icon/{index}")
async def get_entry_icon(item_id: str, index: int) -> FileResponse:
    """Stream the picture one entry of a list points at.

    A list carries an icon per line, so the id alone does not say which; the
    index is the entry's place in the list, which is how the widget drew it.
    """
    return _icon(item_id, index)
