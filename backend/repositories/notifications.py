"""The notification store. The only module that touches it.

In memory, like the board, and pruned on every read: nothing older than the
retention window is ever handed out, so a stale one cannot linger just because
nobody asked for a while.
"""

import uuid
from datetime import UTC, datetime, timedelta

from schemas.notifications import Notification, NotificationCreate

RETENTION = timedelta(hours=48)

_notifications: list[Notification] = []


def _prune(now: datetime) -> None:
    """Drop everything past the window."""
    cutoff = now - RETENTION
    _notifications[:] = [n for n in _notifications if n.created_at > cutoff]


def list_all() -> list[Notification]:
    """Return what is still inside the window, newest first."""
    _prune(datetime.now(UTC))
    return sorted(_notifications, key=lambda n: n.created_at, reverse=True)


def add(data: NotificationCreate) -> Notification:
    """Record one and return it."""
    now = datetime.now(UTC)
    notification = Notification(**data.model_dump(), id=uuid.uuid4().hex[:12], created_at=now)
    _notifications.append(notification)
    _prune(now)
    return notification


def get(notification_id: str) -> Notification | None:
    """Return one, or ``None``."""
    return next((n for n in list_all() if n.id == notification_id), None)


def remove(notification_id: str) -> bool:
    """Dismiss one. Returns whether it was there."""
    before = len(_notifications)
    _notifications[:] = [n for n in _notifications if n.id != notification_id]
    return len(_notifications) < before


def clear() -> int:
    """Dismiss everything. Returns how many went."""
    count = len(_notifications)
    _notifications.clear()
    return count
