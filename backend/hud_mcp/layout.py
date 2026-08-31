"""MCP tools that move, remove, and report on what is already there."""

from mcp.server.mcpserver import MCPServer

from core.hub import hub
from hud_mcp.common import describe
from repositories import board as repo
from schemas.board import ItemUpdate
from services import board as service
from services.board import SlotTakenError


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
    async def move_item(item_id: str, x: int, y: int) -> str:
        """Move an item to a grid cell. Fails if something is already there."""
        return await _patch(item_id, ItemUpdate(x=x, y=y), "moved")

    @server.tool()
    async def resize_item(item_id: str, w: int, h: int) -> str:
        """Resize an item, in grid cells. Fails if it would overlap or overflow."""
        return await _patch(item_id, ItemUpdate(w=w, h=h), "resized")

    @server.tool()
    async def set_parent(parent_id: str, item_id: str) -> str:
        """Record an item as belonging to a box."""
        if repo.get(parent_id) is None:
            return f"No item {parent_id} to parent to."
        return await _patch(item_id, ItemUpdate(parent_id=parent_id), "reparented")

    @server.tool()
    async def remove_item(item_id: str) -> str:
        """Delete an item.

        Removing a box does not delete what it contained: children are orphaned,
        never taken down with it.
        """
        if repo.get(item_id) is None:
            return f"No item {item_id}; nothing removed."
        repo.remove(item_id)
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
        largest = f"{free.w}x{free.h} at ({free.x},{free.y})" if free else "nothing"
        return (
            f"Grid {status.cols}x{status.rows}, {status.item_count} items. "
            f"{status.cells_used}/{status.cells_total} cells used, "
            f"{status.cells_free} free. Largest free rectangle: {largest}."
        )
