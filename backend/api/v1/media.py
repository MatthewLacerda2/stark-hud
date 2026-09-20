"""Everything the media widget needs of the API: its files, and what it reports.

Serving first. The item id is the handle, not the path: a filesystem path never
appears in a URL, and an item that points at a file which has since moved simply
404s. The frontend turns that 404 into a visible placeholder rather than a broken
widget.

And then the one route on this board that runs the other way, ``playback``. It
is here rather than in the generic board router, where it sat behind an ``if
kind != "media"`` — a route about one kind of widget belongs with that widget,
and a router that has to ask what kind of thing it was handed is a router holding
somebody else's route.

Two routers, because they are addressed differently and both addresses are a
contract: what is served lives under ``/media``, and the widget's own state is
under ``/board/items``, which is where the page already posts it.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from repositories import board as repo
from schemas.board import ImagePayload, ItemRead, MediaPayload, PlaybackReport
from schemas.media import media_type
from services import board as service
from services import media as media_service

router = APIRouter(prefix="/media", tags=["media"])

# The widget rather than its files, so it is addressed like every other widget.
playback_router = APIRouter(prefix="/board", tags=["board"])


@playback_router.post("/items/{item_id}/playback", response_model=ItemRead)
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
    item = repo.get(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if not isinstance(item.payload, MediaPayload):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} is a {item.payload.kind}, which plays nothing",
        )
    return await media_service.report(item, payload)


def _stream(path: str) -> FileResponse:
    """Send a file back, named properly, 404ing when it is no longer there.

    Named by this board's own table rather than by ``mimetypes``, which reads
    whatever ``/etc/mime.types`` the machine happens to have and on this one has
    never heard of Matroska. Left to guess, it sends a 7 GB `.mkv` as a stream of
    anonymous bytes and leaves the browser to sniff what it is — which Chromium
    does, right up until the day it does not. A picture has no entry in that
    table and is still guessed, which for `.jpg` nothing gets wrong.
    """
    target = Path(path)
    if not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File is gone: {target}")
    return FileResponse(target, media_type=media_type(path))


@router.get("/background")
async def get_background_media() -> FileResponse:
    """Stream the video behind the grid."""
    background = repo.get_background()
    if background is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No background set")
    return _stream(background.path)


@router.get("/{item_id}")
async def get_media(item_id: str) -> FileResponse:
    """Stream the picture behind an image item.

    Only a picture reaches this route. A film is a track of a player and is
    addressed by the widget's id and its place in the queue, which is what the
    route below is for.
    """
    item = repo.get(item_id)
    if item is None or not isinstance(item.payload, ImagePayload):
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

    The page hangs the track's stamp on the end as a query, which nothing here
    reads and everything here depends on: without it, replacing a queue leaves
    index 0 behind the very same URL, and the browser goes on playing the file it
    already had — with the old file's duration, which is how it is noticed.
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
