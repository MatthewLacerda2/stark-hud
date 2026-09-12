"""The one place on this server where a call still knows its own name.

Every ``add_`` tool funnels through ``common.add()``, and by the time it gets
there the call is gone: what arrives is a payload and four numbers. The name and
the arguments exist together in exactly one spot on the way in —
``MCPServer.call_tool``, which the dispatcher hands every ``tools/call`` to and
which is also what a test calls directly. Everything below it is already too
late, and everything above it speaks JSON-RPC rather than tools.

So this is that method, wrapped, and nothing else. Sixteen tools each passing
their own name would have been sixteen places to forget one, and the seventeenth
tool would have shipped without an origin and nobody would have noticed.

Rejected on the way here: the runner's ``ServerMiddleware`` chain, which does see
``tools/call`` and its raw params but only when a message actually comes down a
transport — ``server.call_tool`` skips it entirely, so every test in this repo
would have been testing a path the board does not use. And a decorator wrapped
around each ``@server.tool()`` at registration, which works and is one place, but
puts a layer between every tool and its own signature for something none of them
care about.
"""

from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult, InputRequiredResult

from services import origin


class OriginServer(MCPServer[Any]):
    """An MCP server whose tool calls say, for their own length, what they were.

    The board reads the origin back out while the tool is still running — see
    ``services.origin`` — so nothing has to be returned from here and the result
    of a call is exactly what it always was.
    """

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: Context[Any, Any] | None = None,
    ) -> CallToolResult | InputRequiredResult:
        """Call the tool, with the call itself readable for as long as it runs."""
        with origin.telling(origin.call(name, arguments)):
            return await super().call_tool(name, arguments, context)
