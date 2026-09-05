"""MCP tools for the notification inbox."""

from typing import cast

from mcp.server.mcpserver import MCPServer

from core.hub import hub
from repositories import notifications as repo
from schemas.notifications import ICONS, NotificationCreate, NotifyLevel
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
        title_color: str | None = None,
        body_color: str | None = None,
    ) -> str:
        """Announce something in the board's inbox.

        Not a widget: every notification goes into the one inbox, like a phone's
        shade. They are kept for 48 hours and then drop out on their own.

        `title` is the line people read; put the detail in `body`. Put your
        project or session name in `source` so a human can tell which of several
        Claudes is speaking.

        `icon` is one of: bell, check, info, alert-triangle, alert-circle,
        x-circle, terminal, git-branch, download, upload, cpu, hard-drive, mail,
        message-square, clock, zap, flame, bug, rocket, wrench — or an absolute
        path to an image on this machine, or SVG markup, which is how you draw
        one this list has no name for. Markup is sanitised on the way in, so
        anything that loads or runs is dropped; paint it with `currentColor` and
        it takes the colour of the line it sits on.

        The text is white unless you colour it. Leave the colours alone unless
        you were asked for one: an inbox where every line is its own colour is
        a mess, and `level` already tints the icon.
        """
        if level not in LEVELS:
            return f"Not sent: level must be info, success, warn or error (got {level!r})"
        try:
            notification = service.create(
                NotificationCreate(
                    title=title,
                    body=body,
                    icon=icon,
                    # The check above is what makes this cast true.
                    level=cast(NotifyLevel, level),
                    source=source,
                    title_color=title_color,
                    body_color=body_color,
                )
            )
        except BadIconError as exc:
            return f"Not sent: {exc}"
        await hub.broadcast("notification.created", notification.model_dump(mode="json"))
        return f"Notified: {title}"

    @server.tool()
    async def list_notifications(query: str | None = None) -> str:
        """What is in the inbox, newest first.

        Pass `query` to keep only the ones whose title, body or source contain
        it — a plain case-insensitive substring. Useful for asking what a
        particular project has been saying, or whether something already
        reported a failure.
        """
        items = repo.search(query) if query else repo.list_all()
        if not items:
            return f"Nothing matching {query!r}." if query else "The inbox is empty."
        lines = [
            f"{n.id}  {n.created_at:%H:%M}  [{n.level}] {n.source or '—'}: {n.title}"
            + (f" — {n.body}" if n.body else "")
            for n in items
        ]
        return "\n".join(lines)

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
