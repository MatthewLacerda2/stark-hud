"""MCP tools for pages: turning the board to one, and moving widgets between them.

A page is a whole board. Nothing is drawn on the television to say which one is
up — no tab, no name, no row of dots — because a page change is a cut and the
room has no pointer to press anyway. A session finds the pages by asking.
"""

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import describe, find
from schemas.board import ItemRead
from services import pages
from services.pages import GroupSplitError, NoRoomError


def register(server: MCPServer) -> None:
    """Attach the page tools to the server."""

    @server.tool()
    async def show_page(page: str = "") -> str:
        """Turn the whole board to another page. One call, and the TV cuts to it.

        A page is a whole board: its widgets, where they sit, the groups they
        fold into. Every widget is on exactly one page and the board shows one
        at a time, so this is how the board carries a screen per subject — the
        ordinary board, a screen for planning a piece of software, a screen for
        a guest — and turns between them.

        Turning to a page nobody has used yet shows an empty board. That is how
        a new page is started: `show_page("planning")`, then build it. Anything
        added lands on the page that is showing.

        A page that is not showing takes no room and draws nothing, so every
        page has the whole grid to itself. It is not asleep: its panels go on
        taking writes by key the whole time, so turning back is a cut to a board
        that is already current rather than a rebuild.

        Call it with no name to come back to the board this one starts on.
        Nothing on the page moves, now or ever — a page keeps its own layout, so
        the one you left is the one you get back.
        """
        # ``services.pages`` sends the one event carrying the board whole, so
        # the television cuts from one page to the next instead of dealing it
        # out a widget at a time.
        board = await pages.show(page)
        drawn = len(pages.drawn(board))
        others = [p for p in pages.names(board) if p != pages.showing()]
        line = (
            f"Showing page {pages.showing()!r} — {drawn} widget{'' if drawn == 1 else 's'} on it."
        )
        return line if not others else f"{line} Also here: {', '.join(repr(p) for p in others)}."

    @server.tool()
    async def move_to_page(item_ids: list[str], page: str) -> str:
        """Move widgets to another page, keeping their size and their place.

        For a widget that belongs on a screen it was not built on. A group
        travels with the widgets it holds, so name the group rather than what is
        inside it.

        Refused, and nothing moves, if they would not fit where they are going:
        nothing is shoved aside on the far page either. Make room there with
        `arrange` first, or send fewer.
        """
        if not item_ids:
            return "Nothing to move: name the widgets that go to the other page."
        found = [find(i) for i in item_ids]
        missing = [i for i, f in zip(item_ids, found, strict=True) if f is None]
        if missing:
            return f"No item {missing[0]}. Call list_items to see what is there."
        wanted = [f for f in found if isinstance(f, ItemRead)]
        try:
            moved = await pages.send(wanted, page)
        except (GroupSplitError, NoRoomError) as exc:
            return str(exc)
        return f"{len(moved)} widgets are on page {moved[0].page!r} now:\n" + "\n".join(
            describe(i) for i in moved
        )
