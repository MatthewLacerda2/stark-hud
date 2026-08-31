"""The MCP server, mounted into the same app that serves the API.

Same process, same board: tools call the services directly, so there is no HTTP
hop and no second copy of the state.
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from hud_mcp import background, content, layout

INSTRUCTIONS = """\
stark-hud is a board shown on a TV in the user's home.

The TV has no keyboard and no mouse and nobody touches it, so whatever you put
there has to make sense unattended. The grid is 12 columns by 8 rows and never
scrolls: anything that does not fit on screen would be invisible forever, so a
full board refuses new items rather than overlapping them.

Placement is in grid cells, never pixels. Omit x and y and the board finds a
free slot for you — prefer that unless you have a reason to arrange things.
Call board_status before adding several items, or anything large.

Nothing is saved. Restarting the server empties the board.

Use notify to tell the user something finished. Those stay until removed, so
they work as an inbox across several sessions; put your project name in the
source field so a human can tell which Claude is speaking.\
"""


def build_server() -> MCPServer:
    """Create the MCP server with every tool registered."""
    server = MCPServer(name="stark-hud", instructions=INSTRUCTIONS)
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
