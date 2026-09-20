"""MCP tools for a list that is kept rather than recomputed.

Every other widget is written whole: whoever has the numbers sends all of them.
A list a person keeps is the exception — it is built up a line at a time, often
by sessions that never saw the other lines — so rewriting the payload to add one
entry would mean knowing every entry, and losing the ones you did not.

The keeping itself is ``services.entries``, which is also what the REST route
and the agent use. What is here is the sentence a model reads back.
"""

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import typed
from schemas.board import ListPayload
from schemas.entries import EntryCreate
from services import entries as service
from services.entries import BadEntryError, NoEntryError


def register(server: MCPServer) -> None:
    """Attach the list tools to the server."""

    @server.tool()
    async def add_to_list(
        item_id: str,
        title: str,
        body: str | None = None,
        icon: str | None = None,
        title_color: str | None = None,
        body_color: str | None = None,
        icon_color: str | None = None,
    ) -> str:
        """Add one entry to the end of a list already on the board.

        This appends: you do not need to know what the list already holds, and
        nothing anybody else put there is lost. Use it for a list somebody is
        keeping — a to-do, a shopping list, things to remember. add_list makes a
        new one; writing the whole payload again is for a panel that gets
        recomputed, not for a list that gets added to.

        `body` is a second, fainter line under the title. `icon` is a name from
        the notification icon set, or an absolute path to a picture on this
        machine. A title on its own is stored as a plain line, so a list of
        plain lines stays one.

        The three colours paint this line's own title, body and icon. Each beats
        the widget's `item_color`; leave them out and the line takes whatever
        colour the list is, which is what most lines want.

        `item_id` is the list's id or its key. Find either with list_items.
        """
        found = typed(item_id, ListPayload)
        if found is None:
            return f"No list {item_id}. Call list_items to see what is there."
        item, _ = found
        try:
            line = EntryCreate(
                title=title,
                body=body,
                icon=icon,
                title_color=title_color,
                body_color=body_color,
                icon_color=icon_color,
            )
            _, held = await service.append(item, line)
        except (BadEntryError, ValueError) as exc:
            return f"Not added: {exc}"
        return f"Added {title!r} to list {item.id} ({held} entries)"

    @server.tool()
    async def remove_from_list(item_id: str, title: str) -> str:
        """Take one entry out of a list, naming the line as it is written.

        Matched on the text itself, ignoring case and the space around it: you
        are removing something you can read on the screen, not an index nobody
        can count from the sofa. The first line that reads that way goes and the
        rest are left alone. Getting the text wrong is safe — the answer says
        what the list actually holds.
        """
        found = typed(item_id, ListPayload)
        if found is None:
            return f"No list {item_id}. Call list_items to see what is there."
        item, _ = found
        try:
            _, left = await service.drop(item, title)
        except NoEntryError as exc:
            return str(exc)
        return f"Removed {title!r} from list {item.id} ({left} left)"
