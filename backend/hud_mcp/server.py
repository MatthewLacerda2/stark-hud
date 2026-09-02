"""The MCP server, mounted into the same app that serves the API.

Same process, same board: tools call the services directly, so there is no HTTP
hop and no second copy of the state.
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from core.config import get_settings
from hud_mcp import (
    background,
    content,
    layout,
    lists,
    media,
    notifications,
    speech,
    wake,
)

# Written to be read by a model that has never seen this board. The grid size is
# interpolated rather than typed out: it has already changed once, and stale
# instructions are worse than none — every session would plan against a grid
# that does not exist.
_INSTRUCTIONS = """\
stark-hud is a board shown on a TV in the user's home.

The TV has no keyboard and no mouse, and from the sofa nobody touches it, so
whatever you put there has to make sense unattended and be readable from across
a room. Prefer few large widgets to many small ones.

The grid is {cols} columns by {rows} rows and never scrolls: anything that does
not fit would be invisible forever, so a full board refuses new items rather
than overlapping them. Placement is in grid cells, never pixels.

Omit x and y and the board finds a free slot — prefer that unless you have a
reason to arrange things. Call board_status before adding several items, or
anything large; it reports the biggest free rectangle so you can pick a size
that fits. A refusal comes back as a sentence saying what is free, not an error.

Someone may drag and resize widgets with a mouse, so do not assume an item is
still where you put it. Call list_items instead of remembering.

Every widget can carry a description: a note that is never drawn on the TV and
only sessions read. Put in it what a later session could not work out by looking
— what a panel is for, what it is waiting on, what its number means. Pass it to
any add_ tool, change or clear it with set_description, and read it back on the
line list_items gives you.

Widgets are dark by convention: this is a TV in a dim room and a pale one glares.
On charts, pass `max` whenever the numbers have a ceiling — without it the axis
fits the data and 21% draws as nearly full.

Anywhere a colour is taken, an eight-digit hex carries its own alpha — `#33ccffaa`
— which lets text and chart marks read through the video the board sits on.

The board is kept on disk and comes back after a restart, widgets and
notifications alike, so what you leave there is what a human finds later.

It holds more than one screenful as pages, and shows exactly one. New widgets
land on the page being shown; show_page turns it, for everyone at once. Only do
that when asked — the TV cannot turn it back.

Widgets are written whole: to change a chart or a feed, write it again with
everything in it. A list somebody is keeping is the exception — add_to_list and
remove_from_list change one line and leave the rest alone, because a list is
built up over time and no session knows every line already in it.

The media widget is the one thing on this board that is driven rather than
written: add_media puts a queue of local audio or video on it and control_media
is its remote, because the television has nothing to press. It plays the queue
through on its own, and list_items reports what it says it is actually doing —
including a file it could not play.

Anything you are about to do that takes more than a moment — reading files,
searching, running a command, working out an answer — call wake_item on the
widget it is going to land in *first*, and then go and do it. The widget
acknowledges on the TV immediately, so the room sees the board take the question
instead of sitting dead until the answer arrives. Every tool here returns in
milliseconds, so the only thing anybody ever waits for is you; this is the one
signal that can go before you know the answer. It settles by itself and it never
replaces the write that follows.
The board also has a voice: speak says one short line out loud through the
television, into a room where somebody may be. Every line is bought from a
speech service on a free tier of a few thousand characters a month, so it is for
something worth interrupting a room for and not for reading back what a tool has
already returned as text. At most 100 characters, refused rather than trimmed —
and the voice reads any language, so write the line in the user's.

Use notify to say something finished. Notifications are not widgets — they all go
into one inbox, like a phone's shade, and drop out after 48 hours. Put your
project name in the source field so a human can tell which Claude is speaking.\
"""


def build_server() -> MCPServer:
    """Create the MCP server with every tool registered."""
    settings = get_settings()
    instructions = _INSTRUCTIONS.format(cols=settings.GRID_COLS, rows=settings.GRID_ROWS)
    server = MCPServer(name="stark-hud", instructions=instructions)
    content.register(server)
    layout.register(server)
    background.register(server)
    lists.register(server)
    media.register(server)
    notifications.register(server)
    wake.register(server)
    speech.register(server)
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
