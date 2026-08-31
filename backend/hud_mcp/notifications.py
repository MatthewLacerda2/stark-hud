"""MCP tools for the notification inbox."""

from mcp.server.mcpserver import MCPServer

from core.hub import hub
from repositories import notifications as repo
from schemas.notifications import ICONS, NotificationCreate
from services import notifications as service
from services.notifications import BadIconError

LEVELS = {"info", "success", "warn", "error"}


def register(server: MCPServer) -> None:
    """Attach the notification tools to the server."""

    @server.tool()
    async def notify(
        title: str,
        body: str | None = None,
        icon: str | None = None,
        level: str = "info",
        source: str | None = None,
    ) -> str:
        """Announce something in the board's inbox.

        Not a tile: every notification goes into the one inbox, like a phone's
        shade. They are kept for 48 hours and then drop out on their own.

        `title` is the line people read; put the detail in `body`. Put your
        project or session name in `source` so a human can tell which of several
        Claudes is speaking.

        `icon` is one of: bell, check, info, alert-triangle, alert-circle,
        x-circle, terminal, git-branch, download, upload, cpu, hard-drive, mail,
        message-square, clock, zap, flame, bug, rocket, wrench — or an absolute
        path to an image on this machine.
        """
        if level not in LEVELS:
            return f"Not sent: level must be info, success, warn or error (got {level!r})"
        try:
            notification = service.create(
                NotificationCreate(title=title, body=body, icon=icon, level=level, source=source)
            )
        except BadIconError as exc:
            return f"Not sent: {exc}"
        await hub.broadcast("notification.created", notification.model_dump(mode="json"))
        return f"Notified: {title}"

    @server.tool()
    async def list_notifications() -> str:
        """What is in the inbox now, newest first."""
        items = repo.list_all()
        if not items:
            return "The inbox is empty."
        return "\n".join(
            f"{n.created_at:%H:%M} [{n.level}] {n.source or '—'}: {n.title}" for n in items
        )

    @server.tool()
    async def dismiss_notification(notification_id: str) -> str:
        """Remove one notification. Use an empty id to clear the whole inbox."""
        if not notification_id:
            removed = repo.clear()
            await hub.broadcast("notifications.cleared", {"removed": removed})
            return f"Inbox cleared ({removed} removed)"
        if not repo.remove(notification_id):
            return f"No notification {notification_id}."
        await hub.broadcast("notification.removed", {"id": notification_id})
        return f"Dismissed {notification_id}"

    _ = ICONS  # the docstring above is the vocabulary; keep them together
