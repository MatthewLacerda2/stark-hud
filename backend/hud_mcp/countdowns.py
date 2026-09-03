"""MCP tools for the countdown stack.

Kept rather than recomputed, for the reason a list is: a countdown is put there
one at a time, often by a session that never saw the others, so rewriting the
payload to add one would mean knowing every entry and losing the ones you did
not.

Nothing here ever writes how long is left. That is a reading of the clock, and
the browser is the only part of this board holding one — see ``CountdownPayload``
for why a countdown fed over the socket would be both wasteful and wrong.
"""

from datetime import datetime

from mcp.server.mcpserver import MCPServer

from core.hub import hub
from hud_mcp.common import add
from repositories import board as repo
from schemas.board import Countdown, CountdownPayload, ItemRead, ItemUpdate
from services import board as service


def _stack(item_id: str) -> ItemRead | None:
    """The item with that id or key, when it is a countdown and not something else."""
    item = repo.get(item_id) or repo.get_by_key(item_id)
    return item if item is not None and item.payload.kind == "countdown" else None


def register(server: MCPServer) -> None:
    """Attach the countdown tools to the server."""

    async def _write(item: ItemRead, entries: list[Countdown]) -> None:
        """Put these entries in place of the old ones and tell every board."""
        payload = item.payload.model_copy(update={"items": entries})
        updated = service.update(item, ItemUpdate(payload=payload))
        await hub.broadcast("item.updated", updated.model_dump(mode="json"))

    @server.tool()
    async def add_countdown(
        title: str | None = None,
        icon: str | None = None,
        empty: str | None = None,
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
        description: str | None = None,
    ) -> str:
        """Put an empty countdown stack on the board, then fill it with add_to_countdown.

        A countdown says how long until something, which is most of what a
        glance at a screen is for. Several stack in one widget rather than each
        taking a slot: what is happening is listed first, then what is still to
        happen, then what is over, and a widget dragged shorter simply shows
        fewer of them — the ones that matter survive, which is what the order is
        for.

        Nothing ever writes the remaining time. Give it the datetimes once and
        the television counts down on its own, so it keeps working long after
        the session that set it has gone.

        `title` is the heading over the stack; `icon` sits beside it.
        """
        try:
            payload = CountdownPayload(title=title, icon=icon, empty=empty)
        except (TypeError, ValueError) as exc:
            return f"Not added: {exc}"
        return await add(payload, x, y, w, h, description=description)

    @server.tool()
    async def add_to_countdown(
        item_id: str,
        title: str,
        start: str,
        end: str | None = None,
        icon: str | None = None,
    ) -> str:
        """Add one thing to a countdown stack, by the widget's id or key.

        `start` is when it begins and `end` is when it is over; leave `end` out
        for a moment rather than a window. Until `start` the widget counts down
        to it; between the two it counts down to `end`; twelve hours after that
        the entry stops being drawn, though it stays here until something takes
        it off.

        Both are ISO 8601 — `2026-09-04T14:00` or `2026-09-04T14:00:00Z`.
        Without a zone it is read as this machine's local time, which is the one
        the television is standing in.
        """
        item = _stack(item_id)
        if item is None:
            return f"No countdown {item_id}. Call list_items to see what is there."
        try:
            entry = Countdown(
                title=title,
                icon=icon,
                start=datetime.fromisoformat(start),
                end=datetime.fromisoformat(end) if end else None,
            )
        except (TypeError, ValueError) as exc:
            return f"Not added: {exc}"
        if entry.end is not None and entry.end <= entry.start:
            return f"Not added: {title!r} would end at or before it starts."
        await _write(item, [*item.payload.items, entry])
        return f"Added {title!r} to {item_id}, which now holds {len(item.payload.items) + 1}"

    @server.tool()
    async def remove_from_countdown(item_id: str, title: str) -> str:
        """Take one thing off a countdown stack, by its title.

        An entry drops out of the drawing by itself twelve hours after it ends.
        This is for taking one off before that — something cancelled, or moved.
        """
        item = _stack(item_id)
        if item is None:
            return f"No countdown {item_id}. Call list_items to see what is there."
        kept = [entry for entry in item.payload.items if entry.title != title]
        if len(kept) == len(item.payload.items):
            held = ", ".join(repr(e.title) for e in item.payload.items) or "nothing"
            return f"No {title!r} in {item_id}. It holds {held}."
        await _write(item, kept)
        return f"Removed {title!r} from {item_id}, which now holds {len(kept)}"
