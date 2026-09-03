"""MCP tools that move, remove, and report on what is already there."""

from mcp.server.mcpserver import MCPServer

from core.hub import hub
from hud_mcp.common import describe
from repositories import board as repo
from schemas.board import ItemUpdate
from services import board as service
from services.board import SlotTakenError
from services.groups import NoRoomError
from services.placement import cells, size


def register(server: MCPServer) -> None:
    """Attach the layout and inspection tools to the server."""

    async def _patch(item_id: str, data: ItemUpdate, verb: str) -> str:
        """Apply an update, broadcast it, and describe the result."""
        item = repo.get(item_id)
        if item is None:
            return f"No item {item_id}. Call list_items to see what is there."
        try:
            updated = service.update(item, data)
        except SlotTakenError as exc:
            return f"Not {verb}: {exc}"
        await hub.broadcast("item.updated", updated.model_dump(mode="json"))
        return f"{verb.capitalize()} {describe(updated)}"

    @server.tool()
    async def move_item(item_id: str, x: float, y: float) -> str:
        """Move an item, in columns and rows. Fails if something is already there."""
        return await _patch(item_id, ItemUpdate(x=x, y=y), "moved")

    @server.tool()
    async def resize_item(item_id: str, w: float, h: float) -> str:
        """Resize an item, in columns and rows. Fails if it would overlap or overflow."""
        return await _patch(item_id, ItemUpdate(w=w, h=h), "resized")

    @server.tool()
    async def set_style(
        item_id: str,
        opacity: float | None = None,
        color: str | None = None,
        background: str | None = None,
        border: str | None = None,
        scale: float | None = None,
    ) -> str:
        """Change how a widget looks. Everything is optional; only what you pass moves.

        `opacity` 0 to 1, how solid its background is. Lower lets the video
        behind show through — charts read fine almost transparent because they
        are mostly their own marks, prose needs something behind it.

        `color` is any CSS colour for the widget's **text**, `var(--chart-2)`
        included.
        An eight-digit hex carries alpha — `#ffffff80` — so the text itself can be
        made to read through rather than over the video the board sits on.

        `background` is what the widget is made of, shown at `opacity`. Left
        alone every widget uses the same card colour, which is what makes a
        board look like one board — so set this only when a widget is meant to
        stand apart from the rest.

        `border` draws a line around the widget in whatever colour is given.
        Almost nothing wants one — a board of outlined rectangles is a form
        rather than a view — so this is for the widget that needs an edge of its
        own. It is the one style `opacity` does not touch, because the point of
        it is a clear line around a widget whose background has been turned
        right down; pass an eight-digit hex if you want the line itself faint.

        `scale` multiplies the text inside, 0.25 to 4. Type already grows with
        the widget; this moves the whole range.
        """
        if opacity is not None and not 0 <= opacity <= 1:
            return f"Not set: opacity must be between 0 and 1 (got {opacity})"
        if scale is not None and not 0.25 <= scale <= 4:
            return f"Not set: scale must be between 0.25 and 4 (got {scale})"
        if (
            opacity is None
            and color is None
            and background is None
            and border is None
            and scale is None
        ):
            return (
                "Nothing to set: pass at least one of opacity, color, background, border or scale"
            )
        update = ItemUpdate(
            opacity=opacity, color=color, background=background, border=border, scale=scale
        )
        return await _patch(item_id, update, "restyled")

    @server.tool()
    async def set_description(item_id: str, description: str = "") -> str:
        """Leave a note on a widget for whoever drives this board next.

        Nobody ever sees it on the TV. It is context a later session cannot get
        back by looking: what this widget is for, what it is waiting on, what
        its number means, that it should be updated after Friday. Write down
        what you would have to explain to yourself in a week.

        It is kept on the widget, not in what the widget shows, so a panel that
        is rewritten every few seconds keeps its note. It comes back with
        list_items, on the same line as the widget, which is where you will find
        one somebody else left.

        Pass nothing, or an empty string, to take the note off. Find the id with
        list_items.
        """
        return await _patch(item_id, ItemUpdate(description=description), "described")

    @server.tool()
    async def remove_item(item_id: str) -> str:
        """Delete an item.

        Removing a group does not delete what it held: its widgets go back on
        the board where they were, which is also why a folded group can only be
        removed while there is still room for them.
        """
        item = repo.get(item_id)
        if item is None:
            return f"No item {item_id}; nothing removed."
        try:
            service.remove(item)
        except NoRoomError as exc:
            return str(exc)
        await hub.broadcast("item.removed", {"id": item_id})
        return f"Removed {item_id}"

    @server.tool()
    async def clear_board() -> str:
        """Remove everything. There is no undo and nothing is saved."""
        removed = repo.clear()
        await hub.broadcast("board.cleared", {"removed": removed})
        return f"Cleared the board ({removed} items removed)"

    @server.tool()
    async def list_items() -> str:
        """List everything on the board, oldest first."""
        items = repo.list_items()
        if not items:
            return "The board is empty."
        return "\n".join(describe(item) for item in items)

    @server.tool()
    async def board_status() -> str:
        """Report how much room is left before you try to add something.

        Worth calling first when adding several items, or anything large.
        """
        status = service.status()
        free = status.largest_free_rect
        largest = (
            f"{size(free.w, free.h)} at ({cells(free.x)},{cells(free.y)})" if free else "nothing"
        )
        return (
            f"Board {size(status.cols, status.rows)}, {status.item_count} items. "
            f"{cells(status.cells_used)}/{cells(status.cells_total)} cells used, "
            f"{cells(status.cells_free)} free. Largest free rectangle: {largest}."
        )
