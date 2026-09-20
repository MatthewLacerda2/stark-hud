"""MCP tools for the countdown stack.

Kept rather than recomputed, for the reason a list is: a countdown is put there
one at a time, often by a session that never saw the others, so rewriting the
payload to add one would mean knowing every entry and losing the ones you did
not. Both kinds of keeping live in ``services.entries``, which the REST route
and the agent use too; what is here is the sentence a model reads back.

Nothing here ever writes how long is left. That is a reading of the clock, and
the browser is the only part of this board holding one — see ``CountdownPayload``
for why a countdown fed over the socket would be both wasteful and wrong.
"""

from datetime import datetime

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import add, typed
from schemas.board import CountdownPayload
from schemas.entries import EntryCreate
from services import entries as service
from services.entries import BadEntryError, NoEntryError


def register(server: MCPServer) -> None:
    """Attach the countdown tools to the server."""

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
        found = typed(item_id, CountdownPayload)
        if found is None:
            return f"No countdown {item_id}. Call list_items to see what is there."
        item, _ = found
        try:
            # Both ways a pair of instants can be wrong are refused by the model
            # itself (schemas.spans), so they arrive as a ValueError like any
            # other bad field — including the one that used to escape as an
            # uncaught TypeError, a start naming a timezone and an end not.
            thing = EntryCreate(
                title=title,
                icon=icon,
                start=datetime.fromisoformat(start),
                end=datetime.fromisoformat(end) if end else None,
            )
            _, held = await service.append(item, thing)
        except (BadEntryError, TypeError, ValueError) as exc:
            return f"Not added: {exc}"
        return f"Added {title!r} to {item.id}, which now holds {held}"

    @server.tool()
    async def remove_from_countdown(item_id: str, title: str) -> str:
        """Take one thing off a countdown stack, by its title.

        An entry drops out of the drawing by itself twelve hours after it ends.
        This is for taking one off before that — something cancelled, or moved.
        """
        found = typed(item_id, CountdownPayload)
        if found is None:
            return f"No countdown {item_id}. Call list_items to see what is there."
        item, _ = found
        try:
            _, held = await service.drop(item, title)
        except NoEntryError as exc:
            return str(exc)
        return f"Removed {title!r} from {item.id}, which now holds {held}"
