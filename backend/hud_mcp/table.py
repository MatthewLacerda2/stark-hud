"""The MCP tool for tables."""

from typing import Any

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import add
from schemas.board import TableColumn, TablePayload


def register(server: MCPServer) -> None:
    """Attach the table tool to the server."""

    @server.tool()
    async def add_table(
        columns: list[dict[str, Any]],
        rows: list[dict[str, str]] | None = None,
        title: str | None = None,
        icon: str | None = None,
        empty: str | None = None,
        title_color: str | None = None,
        icon_color: str | None = None,
        row_color: str | None = None,
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
        description: str | None = None,
    ) -> str:
        """Put rows of text under named columns, lined up in a grid.

        For readings that only mean something side by side — what each program
        is using, what each machine costs, what each run scored. A list can say
        one thing per line; this says four, and they line up down the screen.

        `columns` is the shape of the table, one entry each:

            key     the field to read out of every row
            label   the heading, if the key is not it
            align   "left" (the default) or "right" — numbers want right
            width   its share of the width against the others, 1 unless told

        `rows` are the cells, already written the way they should read: this
        draws "1.7 GB" and "<1%" exactly as given, and never reformats a number
        or works one out. A row with nothing under a column draws an empty cell.

        Only four or five columns fit a board this size before the text is too
        small to read across a room; a sixth is usually a second table.

        To update it, write the whole thing again — as a panel by key, which is
        what something refreshing on a timer should do.
        """
        try:
            payload = TablePayload(
                columns=[TableColumn(**column) for column in columns],
                rows=rows or [],
                title=title,
                icon=icon,
                empty=empty,
                title_color=title_color,
                icon_color=icon_color,
                row_color=row_color,
            )
        except (TypeError, ValueError) as exc:
            return f"Not added: {exc}"
        return await add(payload, x, y, w, h, description=description)
