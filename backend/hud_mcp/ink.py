"""MCP tools for the colour the board writes in."""

from mcp.server.mcpserver import MCPServer
from pydantic import ValidationError

from core.hub import hub
from schemas.board import Ink
from services import board as service


def register(server: MCPServer) -> None:
    """Attach the ink tools to the server."""

    @server.tool()
    async def set_ink(color: str) -> str:
        """Set the colour every widget writes in, unless it was given its own.

        The board's ink is white at 65%, and the fraction is the point: the video
        behind shows through the readout, which is what makes it look displayed
        rather than pasted on. It is settable because the right value depends on
        what is playing behind it — a bright or heavily saturated background eats
        a translucent ink, and the fix should take a sentence rather than a
        rebuild.

        Pass a colour with alpha to keep that: `#ffffffa6` is white at 65%,
        `#ffffff` is white and will sit on the picture rather than in it. Naming
        one of the board's own colours works here as everywhere — `foreground`,
        `muted-foreground`, `chart-2` — and a named colour follows the theme.

        This is the default and never an override: a widget told its own colour
        with set_style keeps exactly that colour.
        """
        try:
            ink = Ink(color=color)
        except ValidationError as exc:
            return f"Not set: {exc.errors()[0]['msg']}"
        service.set_ink(ink)
        await hub.broadcast("ink.changed", ink.model_dump(mode="json"))
        return f"The board now writes in {ink.color}"

    @server.tool()
    async def clear_ink() -> str:
        """Go back to the board's own ink, which is white at 65%."""
        service.set_ink(None)
        await hub.broadcast("ink.changed", None)
        return "Ink back to the default, white at 65%"
