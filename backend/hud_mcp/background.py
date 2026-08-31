"""MCP tools for the video behind the grid."""

from mcp.server.mcpserver import MCPServer

from core.hub import hub
from schemas.board import Background
from services import board as service
from services.board import MissingFileError


def register(server: MCPServer) -> None:
    """Attach the background tools to the server."""

    @server.tool()
    async def set_background(path: str, blur: bool = False) -> str:
        """Play a local video behind the board, on a loop and always silent.

        Blur it when items sit on top, which is most of the time: an unblurred
        video competes with the text in front of it. Leave it sharp only when
        the video is the point.

        The path must exist on the machine running the board.
        """
        try:
            service.set_background(Background(path=path, blur=blur))
        except MissingFileError as exc:
            return f"Not set: {exc}"
        await hub.broadcast("background.changed", {"path": path, "blur": blur})
        return f"Background set to {path}" + (" (blurred)" if blur else " (sharp)")

    @server.tool()
    async def clear_background() -> str:
        """Drop the video and go back to the plain dark ground."""
        service.set_background(None)
        await hub.broadcast("background.changed", None)
        return "Background cleared"
