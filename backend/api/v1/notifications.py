"""Notification endpoints. One inbox, many writers.

Nothing is announced from here: ``services.notifications`` puts each line on the
socket as it records it, so the route and the ``notify`` tool cannot drift.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from repositories import notifications as repo
from schemas.notifications import Inbox, Notification, NotificationCreate
from services import notifications as service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Inbox)
async def list_notifications() -> Inbox:
    """Everything announced in the retention window, newest first."""
    return service.inbox()


@router.post("", response_model=Notification, status_code=status.HTTP_201_CREATED)
async def create_notification(payload: NotificationCreate) -> Notification:
    """Announce something."""
    return await service.create(payload)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss(notification_id: str) -> None:
    """Dismiss one."""
    if not await service.dismiss(notification_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such notification")


@router.delete("", response_model=dict[str, int])
async def dismiss_all() -> dict[str, int]:
    """Dismiss everything."""
    return {"removed": await service.clear()}


@router.get("/{notification_id}/icon")
async def get_icon(notification_id: str) -> FileResponse:
    """Stream the image a notification points at, when its icon is a path."""
    notification = repo.get(notification_id)
    if notification is None or not notification.icon or not notification.icon.startswith("/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No image for that id")
    path = Path(notification.icon)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File is gone: {path}")
    return FileResponse(path)
