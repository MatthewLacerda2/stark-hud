"""Notification rules: what an icon may be, and turning one into an inbox."""

from pathlib import Path

from repositories import notifications as repo
from schemas.notifications import ICONS, Inbox, Notification, NotificationCreate

RETENTION_HOURS = repo.RETENTION.total_seconds() / 3600


class BadIconError(Exception):
    """Raised when an icon is neither a known name nor a file that exists."""

    def __init__(self, icon: str) -> None:
        self.icon = icon
        super().__init__(
            f"{icon!r} is not an icon: pass one of {', '.join(sorted(ICONS))}, "
            "or an absolute path to an image file"
        )


def create(data: NotificationCreate) -> Notification:
    """Record a notification, refusing an icon that would not draw.

    Checked here rather than at render: a name with a typo would silently show
    nothing, and the caller would never learn why.
    """
    if data.icon is not None and data.icon not in ICONS:
        if not data.icon.startswith("/") or not Path(data.icon).is_file():
            raise BadIconError(data.icon)
    return repo.add(data)


def inbox() -> Inbox:
    """Everything still inside the retention window."""
    return Inbox(notifications=repo.list_all(), retention_hours=RETENTION_HOURS)
