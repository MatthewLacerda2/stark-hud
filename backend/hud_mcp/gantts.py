"""The MCP tool for the gantt.

One tool, and the whole widget in one argument. A gantt is dictated in one
breath — *"tonight: sauce six to quarter to seven, laundry half six to half
seven"* — so the session that writes it already knows every row and every bar.
That is the opposite of a list, which is built up over days by sessions that
never saw each other's lines and so needs `add_to_list`; it is the same
situation a chart is in, and a chart is written whole.

Nothing here ever writes how long something lasts. That is a reading of the
clock against two instants, and the browser holds the only clock on this board —
see ``GanttPayload``.
"""

from typing import cast

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import add
from schemas.board import GanttPayload, GanttRow


def register(server: MCPServer) -> None:
    """Attach the gantt tool to the server."""

    @server.tool()
    async def add_gantt(
        rows: list[dict],
        title: str | None = None,
        icon: str | None = None,
        empty: str | None = None,
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
        description: str | None = None,
    ) -> str:
        """Draw the next stretch of time as named rows of bars.

        This is the widget for two things happening at once. A countdown says
        *when* one thing is; a gantt says how long each thing runs and which of
        them overlap, so from the sofa the shape of an evening is readable
        without reading a word.

        `rows` is the whole widget, written in one call:

            [{"name": "Kitchen", "bars": [
                {"title": "sauce", "start": "18:00", "end": "18:45"},
                {"title": "bake", "start": "18:45", "end": "19:30"}]},
             {"name": "Laundry", "bars": [
                {"title": "wash", "start": "18:30", "end": "19:30",
                 "color": "chart-3"}]}]

        A bar needs both `start` and `end` — width is the only thing here that
        carries duration, so a bar with no end has nothing to draw. Both are ISO
        8601: `2026-09-04T18:00` or `2026-09-04T18:00:00Z`. Without a zone it is
        read as this machine's local time, which is the one the television is
        standing in. Bars inside a row may overlap; so may rows, and that is
        what the widget is for.

        Give it the datetimes once and the television works out the rest on its
        own, for as long as the widget is up. The left edge is always now, so
        the evening plays itself out with nothing further written to it: a bar
        that has started clips at that edge, one that is over stops being drawn,
        and the scale re-tunes itself as the near things fall off — an hour wide
        while tonight is busy, four hours wide once only one thing is left. That
        is also why there is no tool to change a bar: to change the plan, remove
        the widget and add it again.

        A bar says its own name when it is wide enough to hold one, and shows
        only its colour and its place when it is not — which is all anybody
        wants about something four hours out.

        `color` on a bar is optional. Left out it takes its row's colour from
        the board's own palette, which is what keeps a row reading as one track;
        pass one when a particular bar has to be told apart. An eight-digit hex
        carries its own alpha — `#33ccffaa` — which leaves the video behind the
        board showing through.

        `title` is the heading over the widget and `icon` sits beside it.
        `empty` is what it says when nothing is coming up.
        """
        try:
            # Pydantic builds the rows out of these dicts and says which field was
            # wrong when it cannot; the cast is only how that gets said to mypy.
            payload = GanttPayload(
                title=title, icon=icon, empty=empty, rows=cast(list[GanttRow], rows)
            )
        except (TypeError, ValueError) as exc:
            return f"Not added: {exc}"
        return await add(payload, x, y, w, h, description=description)
