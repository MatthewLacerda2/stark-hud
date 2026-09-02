"""The one tool here that writes nothing.

Every other tool on this server returns in milliseconds, because the server runs
inside the process that draws the board. So the wait somebody on the sofa sits
through is never a tool call — it is the session between two of them, reading
files and working out what to say. An acknowledgement fired when a write starts
would be replaced by that write in the same frame and buy nobody anything.

This is the signal that can go first. It carries no content and changes nothing
on the board, which is exactly why a session can afford to send it before it
knows the answer.
"""

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import find, wake


def register(server: MCPServer) -> None:
    """Attach the acknowledgement tool to the server."""

    @server.tool()
    async def wake_item(target: str) -> str:
        """Tell a widget you are about to work on it — before you do the work.

        Call this the moment you know where an answer is going to land and
        *before* the slow part: the reading, the searching, the shelling out,
        the other tool calls, the thinking. The widget acknowledges on the TV
        straight away, so the room sees the board take the question instead of
        sitting dead for six seconds while you think.

        Called after the write, it only flickers over an answer that is already
        there, and it is never a substitute for writing the answer. It is worth
        nothing on its own — the write still has to follow.

        `target` is an item id or the key of a panel, whichever you have.
        list_items reports both.

        The widget settles by itself after about ten seconds, so a session that
        wakes something and then dies leaves nothing glowing overnight. Wake it
        again if the work runs longer than that.
        """
        item = find(target)
        if item is None:
            return (
                f"Nothing called {target!r} to wake. Only a widget already on the "
                f"board can acknowledge anything; call list_items to see what is."
            )
        await wake(item)
        return f"Waking {item.payload.kind} {item.id}"
