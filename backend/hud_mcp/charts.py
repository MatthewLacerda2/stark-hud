"""The MCP tool for charts.

Its own module rather than one more tool in ``content.py``: a chart is the one
widget on this board with a vocabulary of its own — five kinds, four axis
settings, thresholds, and a radial that is not a series at all but a gauge — and
the description of that vocabulary is most of what a session reads before it
draws one.
"""

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import add
from schemas.board import ChartPayload


def register(server: MCPServer) -> None:
    """Attach the chart tool to the server."""

    @server.tool()
    async def add_chart(
        chart: str,
        data: list[dict[str, float | int | str]],
        x_key: str,
        series: list[str],
        title: str | None = None,
        icon: str | None = None,
        max: float | None = None,
        unit: str | None = None,
        axes: str = "both",
        colors: list[str] | None = None,
        thresholds: list[dict] | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        description: str | None = None,
    ) -> str:
        """Draw a chart from data you supply inline.

        The board never fetches or polls: send the numbers. `chart` is line, bar,
        pie, area or radial. `x_key` names the field on the x axis and `series`
        names the fields to plot. To update a chart, remove it and add it again.

        `axes` says which axes a line, bar or area chart draws: both (the
        default), x, y or none. Leave it out unless the numbers read on their
        own without a scale — a pie has no axes and ignores it.

        `colors` is one CSS colour per series. An eight-digit hex carries alpha —
        `#33ccffaa` — which leaves the video behind the board showing through the
        marks.

        `thresholds` is how a chart on this board is allowed to shout. The board
        is deliberately one tone, so a colour that appears means something went
        past a line. Pass a list of `{"at": 90, "color": "#ff5c33"}`: a mark
        above `at` takes that colour, and anything under every threshold keeps
        the colour it already had. Give two and the highest one a value clears
        wins, which is how an attention level and an alarm level live on the
        same chart.

        `at` is in the units of the plotted value, not of what the number means
        to a human. The memory gauge plots a percentage, so "above 12 GB of
        15.6" is `at: 77`, not `at: 12`.

        Only bar and radial read `thresholds`. A bar decides one bar at a time,
        so a single hot core turns while the rest stay as they were, and a gauge
        decides on its one value. A pie and a line chart already give every
        series a colour of its own — that is what those charts are for — so they
        ignore the field completely rather than half-honouring it.

        A radial is a gauge: it reads the first row of `data` only and draws it
        as an arc of a ring whose ceiling is `max`, so always pass `max`. The
        ring is the message — it says the proportion from across the room — and
        the middle of it is who the gauge is: `icon` and `title` side by side,
        with `data[0][x_key]` under them for when a number is genuinely wanted,
        the way "3.7 of 15.6 GB" is. Keep `title` to about six characters; a
        longer one is not refused, it just runs out of ring to sit in. `unit`
        does nothing on a radial, because there is no bare number for it to sit
        against.

        Every other chart says what it is at the origin instead: the corner
        where the axes meet, left of the first bar and below the baseline, which
        is empty space the plot already reserves. `icon` sits at the bottom of
        that corner and `title` stacks above it, anchored there — a longer title
        grows upward into the plot rather than pushing it down, so neither of
        them costs the chart any height. That is what lets a CPU widget be a
        slim strip of bars and still say it is the CPU. Pass either, both or
        neither; all four are meaningful. A pie has no axes and so no origin,
        but it has the same empty corner and uses it.

        `icon` is a name from the notification icon set, an absolute path to a
        picture on this machine, or SVG markup — `<svg viewBox="0 0 24 24" ...>`
        with paths and shapes in it, which is how you draw something the icon
        set has no name for. It is sanitised on the way in, so anything that
        loads or runs is dropped. Paint it with `currentColor` and it takes the
        widget's colour.
        """
        if chart not in {"line", "bar", "pie", "area", "radial"}:
            return f"Not added: chart must be line, bar, pie, area or radial (got {chart!r})"
        if axes not in {"both", "x", "y", "none"}:
            return f"Not added: axes must be both, x, y or none (got {axes!r})"
        # A typo in an icon or a colour comes back as the sentence the validator
        # wrote, rather than as a stack trace on the caller's side.
        try:
            payload = ChartPayload(
                chart=chart,
                data=data,
                x_key=x_key,
                series=series,
                title=title,
                icon=icon,
                max=max,
                unit=unit,
                axes=axes,
                colors=colors or [],
                thresholds=thresholds or [],
            )
        except (TypeError, ValueError) as exc:
            return f"Not added: {exc}"
        return await add(payload, x, y, w, h, description=description)
