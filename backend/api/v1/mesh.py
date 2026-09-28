"""Serve the model file behind a mesh widget.

Addressed by the widget's id, never by the path it holds — the same rule the
media routes follow, and for the same reason: a filesystem path is not something
to put in a URL that anybody on the LAN can type.

Read off the disk on every request rather than cached. A browser asks when the
widget appears and when it is told the file was written again, and a cache
would mean exporting from Blender and watching the board go on showing the old
model.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from repositories import board as repo
from schemas.mesh import MeshPayload
from services import mesh as service

router = APIRouter(prefix="/mesh", tags=["mesh"])


@router.get("/{item_id}")
async def get_mesh(item_id: str) -> FileResponse:
    """The model file for one mesh widget, as it is on disk.

    A file that is no longer there takes the widget with it: this is the one
    file-backed widget that removes itself rather than showing a placeholder,
    which is what the owner of this board asked for. ``services.mesh.forget``
    records why, takes the widget off the board and says so on the socket —
    clients drop it on ``item.removed`` without waiting for this 404.
    """
    item = repo.get(item_id)
    if item is None or not isinstance(item.payload, MeshPayload):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No mesh for that id")
    found = service.file_of(item.payload.path)
    if found is None:
        gone = await service.forget(item, item.payload.path)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=gone)
    target, kind = found
    # `no-store`: the same URL is asked again after a re-export, and a cached
    # answer there is the old model drawn as though it were the new one.
    return FileResponse(target, media_type=kind, headers={"Cache-Control": "no-store"})
