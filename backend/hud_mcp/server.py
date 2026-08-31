"""The MCP server, mounted into the same app that serves the API.

Same process, same board: tools call the services directly, so there is no HTTP
hop and no second copy of the state.
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from core.config import get_settings
from hud_mcp import background, content, layout

# Written to be read by a model that has never seen this board. The grid size is
# interpolated rather than typed out: it has already changed once, and stale
# instructions are worse than none — every session would plan against a grid
# that does not exist.
_INSTRUCTIONS = """\
stark-hud is a board shown on a TV in the user's home.

The TV has no keyboard and no mouse, and from the sofa nobody touches it, so
whatever you put there has to make sense unattended and be readable from across
a room. Prefer few large tiles to many small ones.

The grid is {cols} columns by {rows} rows and never scrolls: anything that does
not fit would be invisible forever, so a full board refuses new items rather
than overlapping them. Placement is in grid cells, never pixels.

Omit x and y and the board finds a free slot — prefer that unless you have a
reason to arrange things. Call board_status before adding several items, or
anything large; it reports the biggest free rectangle so you can pick a size
that fits. A refusal comes back as a sentence saying what is free, not an error.

Someone may drag and resize tiles with a mouse, so do not assume an item is
still where you put it. Call list_items instead of remembering.

Tiles are dark by convention: this is a TV in a dim room and a pale one glares.
On charts, pass `max` whenever the numbers have a ceiling — without it the axis
fits the data and 21% draws as nearly full.

Nothing is saved. Restarting the server empties the board.

Use notify to say something finished. Those stay until removed, so they work as
an inbox across several sessions; put your project name in the source field so a
human can tell which Claude is speaking.\
"""


def build_server() -> MCPServer:
    """Create the MCP server with every tool registered."""
    settings = get_settings()
    instructions = _INSTRUCTIONS.format(cols=settings.GRID_COLS, rows=settings.GRID_ROWS)
    server = MCPServer(name="stark-hud", instructions=instructions)
    content.register(server)
    layout.register(server)
    background.register(server)
    return server


def build_app() -> Starlette:
    """Return the ASGI app to mount at /mcp.

    Host checking is off deliberately. The board is open to the LAN by design,
    so validating the Host header would only give a false sense of safety:
    anything that can reach the port can already drive the board.
    """
    return build_server().streamable_http_app(
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
            allowed_hosts=["*"],
            allowed_origins=["*"],
        ),
    )
