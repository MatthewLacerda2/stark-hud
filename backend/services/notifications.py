"""Notification rules: what an icon may be, and turning one into an inbox."""

from pathlib import Path

from repositories import notifications as repo
from schemas import svg
from schemas.icon import UNKNOWN
from schemas.notifications import ICONS, Inbox, Notification, NotificationCreate

RETENTION_HOURS = repo.RETENTION.total_seconds() / 3600


class BadIconError(Exception):
    """Raised when an icon is neither a known name, a file that exists, nor SVG we can read."""

    def __init__(self, icon: str, reason: str | None = None) -> None:
        self.icon = icon
        super().__init__(reason or f"{icon!r} " + UNKNOWN.format(names=", ".join(sorted(ICONS))))


def _stored(icon: str) -> str:
    """What to keep for an icon, refusing one that would draw nothing.

    The same three forms every widget's icon has, checked here rather than at
    render: a name with a typo would silently show nothing, and the caller would
    never learn why. A notification asks one more question than a widget does —
    whether the file is actually there — because it is announced once and never
    written again.

    Markup is the form that changes on the way through: what is stored is the
    sanitised icon, never what arrived.
    """
    if svg.looks_like_svg(icon):
        try:
            return svg.sanitise(icon)
        except ValueError as exc:
            raise BadIconError(icon, str(exc)) from exc
    if icon in ICONS:
        return icon
    if icon.startswith("/") and Path(icon).is_file():
        return icon
    raise BadIconError(icon)


def create(data: NotificationCreate) -> Notification:
    """Record a notification, refusing an icon that would not draw."""
    if data.icon is not None:
        data = data.model_copy(update={"icon": _stored(data.icon)})
    return repo.add(data)


def inbox() -> Inbox:
    """Everything still inside the retention window."""
    return Inbox(notifications=repo.list_all(), retention_hours=RETENTION_HOURS)
