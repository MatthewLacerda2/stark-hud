"""MCP tools for a list that is kept rather than recomputed.

Every other widget is written whole: whoever has the numbers sends all of them.
A list a person keeps is the exception — it is built up a line at a time, often
by sessions that never saw the other lines — so rewriting the payload to add one
entry would mean knowing every entry, and losing the ones you did not.
"""

from mcp.server.mcpserver import MCPServer

from core.hub import hub
from repositories import board as repo
from schemas.board import ItemRead, ItemUpdate, ListEntry, ListPayload
from services import board as service


def _text(entry: str | ListEntry) -> str:
    """The line as it reads on the screen, whichever shape the entry has."""
    return entry if isinstance(entry, str) else entry.title


def register(server: MCPServer) -> None:
    """Attach the list tools to the server."""

    def _list(item_id: str) -> tuple[ItemRead, ListPayload] | None:
        """The item with that id, when it is a list and not something else.

        The payload comes back beside the item: the check that it *is* a list
        happens here, and returning only the item throws that away — every
        caller would then read `.items` off a union of thirteen payload kinds.
        """
        item = repo.get(item_id)
        if item is None or not isinstance(item.payload, ListPayload):
            return None
        return item, item.payload

    async def _write(item: ItemRead, entries: list[str | ListEntry]) -> None:
        """Put these entries in place of the old ones and tell every board."""
        payload = item.payload.model_copy(update={"items": entries})
        updated = service.update(item, ItemUpdate(payload=payload))
        await hub.broadcast("item.updated", updated.model_dump(mode="json"))

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

        Find the id with list_items.
        """
        found = _list(item_id)
        if found is None:
            return f"No list {item_id}. Call list_items to see what is there."
        item, shown = found
        entry: str | ListEntry = title
        extras = (body, icon, title_color, body_color, icon_color)
        if any(extra is not None for extra in extras):
            try:
                entry = ListEntry(
                    title=title,
                    body=body,
                    icon=icon,
                    title_color=title_color,
                    body_color=body_color,
                    icon_color=icon_color,
                )
            except ValueError as exc:
                return f"Not added: {exc}"
        entries = [*shown.items, entry]
        await _write(item, entries)
        return f"Added {title!r} to list {item_id} ({len(entries)} entries)"

    @server.tool()
    async def remove_from_list(item_id: str, title: str) -> str:
        """Take one entry out of a list, naming the line as it is written.

        Matched on the text itself, ignoring case and the space around it: you
        are removing something you can read on the screen, not an index nobody
        can count from the sofa. The first line that reads that way goes and the
        rest are left alone. Getting the text wrong is safe — the answer says
        what the list actually holds.
        """
        holder = _list(item_id)
        if holder is None:
            return f"No list {item_id}. Call list_items to see what is there."
        item, shown = holder
        entries = list(shown.items)
        wanted = title.strip().casefold()
        found = next(
            (i for i, entry in enumerate(entries) if _text(entry).strip().casefold() == wanted),
            None,
        )
        if found is None:
            held = ", ".join(repr(_text(entry)) for entry in entries) or "nothing"
            return f"No entry {title!r} in list {item_id}. It holds: {held}"
        del entries[found]
        await _write(item, entries)
        return f"Removed {title!r} from list {item_id} ({len(entries)} left)"
