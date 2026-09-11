"""The MCP tool for the flow.

One tool, and the whole diagram in two arguments. A flow is dictated in one
breath — *"clone, then build, then test, and if the test fails it goes back to
build"* — so the session writing it already knows every box and every arrow.
That is the same situation a chart and a gantt are in, and both are written
whole; it is the opposite of a list, which is built up over days by sessions
that never saw each other's lines.

There is deliberately no ``add_to_flow`` and no ``set_flow_node``. A flow that
changes is rewritten whole by ``key``, which the panel path already does.
"""

from typing import cast

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import add
from schemas.board import FlowLink, FlowNode, FlowPayload


def register(server: MCPServer) -> None:
    """Attach the flow tool to the server."""

    @server.tool()
    async def add_flow(
        nodes: list[dict],
        links: list[dict],
        title: str | None = None,
        icon: str | None = None,
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
        description: str | None = None,
    ) -> str:
        """Draw a diagram: named boxes, and arrows saying one leads to another.

        This is the widget for the thing no other one here can say — *this leads
        to that*. A deployment, a morning routine, the shape of a pipeline, a
        decision with two ways out. The whole diagram lives inside one widget;
        nothing is placed on the board per box and nothing overlaps anything.

        `nodes` are the boxes and `links` are the arrows:

            nodes = [{"id": "clone", "text": "Clone"},
                     {"id": "build", "text": "Build"},
                     {"id": "test",  "text": "Test", "shape": "ellipse"},
                     {"id": "ship",  "text": "Ship", "color": "success"}]
            links = [{"source": "clone", "target": "build"},
                     {"source": "build", "target": "test"},
                     {"source": "test",  "target": "ship", "label": "green"},
                     {"source": "test",  "target": "build", "label": "red",
                      "curve": "s", "color": "destructive"}]

        A link says `source` and `target`, never `from` — `from` is a keyword in
        the language this board is written in, and one spelling everywhere beats
        the nicer word. `label` is a word on the arrow, dropped by the widget
        when the arrow is too short to hold it. `curve` is "straight" (the
        default) or "s", which leaves each box along the side it meets — what
        two boxes side by side want. `heads` is "end" (the default), "none" for a
        plain connecting line, or "both".

        Say nothing about where the boxes sit and the widget lays them out in one
        evenly spaced line along its longer side, which is worth looking at and
        is all this tool promises. To place them yourself, give every node all
        four of `x`, `y`, `w`, `h` as fractions of the widget from its top-left:

            {"id": "build", "text": "Build", "x": 0.1, "y": 0.4,
             "w": 0.25, "h": 0.2}

        All four or none, and every node or no node — a half-placed flow has no
        honest reading. Every edge has to land inside 0-1, the far ones
        included: this widget is clipped and nobody can scroll the television.
        Boxes may overlap each other and that is allowed; the author put them
        both there.

        An arrow picks the pair of facing sides on its own. Name
        `source_side`/`target_side` — "left", "right", "top", "bottom" or
        "center" — only when you want one somewhere else; "center" points *at* a
        box rather than touching it, so the arrow is drawn across it.

        `shape` is "rectangle" (the default) or "ellipse", and `radius` rounds a
        rectangle's corners as a fraction of the box's own shorter side: 0 is
        square and 0.5 is a pill. There is no third shape on purpose — a branch
        is said by the words on the two arrows leaving a box, and a flowchart
        that needs a legend has stopped being readable from a sofa.

        `color` on a node washes its interior and draws its outline in the same
        colour at full strength; left out it is the widget's own ink, which over
        the board's video is a pane of smoked glass. `color` on a link is the
        arrow, always at full strength — an arrow is a mark and marks are never
        washed.

        `title` is the heading over the widget and `icon` sits beside it. Give
        neither and the widget draws no chrome at all, which is usually what a
        diagram wants.

        To change a flow, write it again with everything in it.
        """
        try:
            # Pydantic builds the nodes and links out of these dicts and says
            # which field was wrong when it cannot; the casts are only how that
            # gets said to mypy.
            payload = FlowPayload(
                title=title,
                icon=icon,
                nodes=cast(list[FlowNode], nodes),
                links=cast(list[FlowLink], links),
            )
        except (TypeError, ValueError) as exc:
            return f"Not added: {exc}"
        return await add(payload, x, y, w, h, description=description)
