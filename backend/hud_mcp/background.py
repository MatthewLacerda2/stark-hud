"""MCP tools for the video behind the grid."""

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import ON_HOST
from schemas.board import Background
from services import board as service
from services.board import MissingFileError


def register(server: MCPServer) -> None:
    """Attach the background tools to the server."""

    @server.tool(annotations=ON_HOST)
    async def set_background(path: str, blur: bool = False) -> str:
        """Play a local video behind the board, on a loop and always silent.

        Blur it when items sit on top, which is most of the time: an unblurred
        video competes with the text in front of it. Leave it sharp only when
        the video is the point.

        The path must exist on the machine running the board.
        """
        try:
            await service.set_background(Background(path=path, blur=blur))
        except MissingFileError as exc:
            return f"Not set: {exc}"
        return f"Background set to {path}" + (" (blurred)" if blur else " (sharp)")

    @server.tool()
    async def clear_background() -> str:
        """Drop the video and go back to the plain dark ground."""
        await service.set_background(None)
        return "Background cleared"
