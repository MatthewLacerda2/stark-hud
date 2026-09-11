"""Serve the geometry behind a mesh widget.

Addressed by the widget's id, never by the path it holds — the same rule the
media routes follow, and for the same reason: a filesystem path is not something
to put in a URL that anybody on the LAN can type.

Geometry is read off the disk on every request rather than cached. A wireframe
is rebuilt in about a millisecond, a browser asks for one when the widget mounts
and not again, and a cache would mean editing a model in Blender and watching
the board go on showing the old one.
"""

from fastapi import APIRouter, HTTPException, status

from core.hub import hub
from repositories import board as repo
from schemas.mesh import MeshPayload, Wireframe
from services import mesh as service

router = APIRouter(prefix="/mesh", tags=["mesh"])


@router.get("/{item_id}")
async def get_mesh(item_id: str) -> Wireframe:
    """The wireframe for one mesh widget, as parts of points and lines.

    A file that is no longer there takes the widget with it: this is the one
    file-backed widget that removes itself rather than showing a placeholder,
    which is what the owner of this board asked for. ``services.mesh.forget``
    records why, and what it costs on a machine with a bind-mounted drive.

    The removal is broadcast here rather than in the service for the reason every
    other mutation is: the service decides and mutates, the handler tells the
    room. Clients drop the widget on ``item.removed`` without waiting for this
    response, which is just as well — this one is a 404.
    """
    item = repo.get(item_id)
    if item is None or not isinstance(item.payload, MeshPayload):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No mesh for that id")
    found = service.read(item.payload.path)
    if found is None:
        gone = service.forget(item, item.payload.path)
        await hub.broadcast("item.removed", {"id": item_id})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=gone)
    return found
