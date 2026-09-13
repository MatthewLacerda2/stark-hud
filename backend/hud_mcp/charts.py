"""The MCP tool for charts.

Its own module rather than one more tool in ``content.py``: a chart is the one
widget on this board with a vocabulary of its own — six kinds, four axis
settings, thresholds, and two polar ones that are not series at all: a radial
that is a gauge and a radar that is a shape — and the description of that
vocabulary is most of what a session reads before it draws one.
"""

from typing import cast, get_args

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import add
from schemas.board import ChartAxes, ChartKind, ChartPayload, ChartThreshold

# Read off the Literals rather than written out again. The list of kinds used to
# live here as well as in `schemas/chart.py`, so adding one meant remembering to
# edit two places — and a rule kept by memory is the kind that quietly stops
# being kept. Now there is one list and this reads it.
KINDS: tuple[str, ...] = get_args(ChartKind)
AXES: tuple[str, ...] = get_args(ChartAxes)


def _one_of(options: tuple[str, ...]) -> str:
    """The options as a sentence lists them: "line, bar, pie, area or radial"."""
    return f"{', '.join(options[:-1])} or {options[-1]}"


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
        unfilled: str | None = None,
        thresholds: list[dict] | None = None,
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
        description: str | None = None,
    ) -> str:
        """Draw a chart from data you supply inline.

        The board never fetches or polls: send the numbers. `chart` is line, bar,
        pie, area, radial or radar. `x_key` names the field on the x axis and
        `series` the fields to plot. To update a chart, remove it and add it
        again.

        `axes` — both (the default), x, y or none — is read by line, bar and
        area only; leave it out unless the numbers read without a scale.

        `colors` is one CSS colour per series. An eight-digit hex carries alpha
        (`#33ccffaa`), which lets the video behind the board show through.

        `thresholds` is how a chart is allowed to shout on a board that is
        deliberately one tone: `[{"at": 90, "color": "#ff5c33"}]` turns any mark
        above `at` that colour, and the highest threshold cleared wins, so an
        attention level and an alarm level can share a chart. `at` is in the
        plotted units — a gauge plotting a percentage says `at: 77`, not
        `at: 12` for 12 GB. Only bar and radial read it: a bar decides bar by
        bar and a gauge on its one value; pie and line already colour every
        series and ignore it.

        A radial is a gauge: each row of `data` is a ring, an arc of a circle
        whose ceiling is `max` — always pass `max`. Up to three rings,
        concentric and touching, first row outermost, each with its own colour
        and its own threshold; a fourth row is refused. `unfilled` is the rest
        of the ring, translucent white unless told otherwise (`#ffffff40` is a
        quarter, `#ffffff80` a half) — keep it translucent, or the gauge becomes
        a dark disc with a bright edge. The middle is who the gauge is: `icon`
        and `title` side by side, with `data[0][x_key]` under them for a
        spelled-out reading like "3.7 of 15.6 GB". With more than one ring that
        reading is not drawn, so make `title` name the set ("Machine", not
        "RAM"), about six characters. `unit` does nothing on a radial.

        A radar is a shape, not a reading: one row per spoke, one series, a
        polygon inside a grid that stays visible so an idle machine is a small
        polygon in a reticle rather than an empty widget. Pass `max` as the
        outer ring, send the rows in the order they should go round
        (neighbouring spokes read as one lobe), and expect `axes` and a second
        series to be ignored.

        Every other chart says what it is in its top-left corner: `icon` above
        `title`, anchored there, so a long title grows down over the plot and
        costs the chart no height — a CPU widget can be a slim strip of bars
        and still say it is the CPU. Either, both or neither is fine.

        `icon` is a name from the notification icon set, an absolute path to a
        picture on this machine, or SVG markup (`<svg viewBox="0 0 24 24" ...>`),
        sanitised so nothing that loads or runs survives. Paint it with
        `currentColor` and it takes the widget's colour.
        """
        if chart not in KINDS:
            return f"Not added: chart must be {_one_of(KINDS)} (got {chart!r})"
        if axes not in AXES:
            return f"Not added: axes must be {_one_of(AXES)} (got {axes!r})"
        # A typo in an icon or a colour comes back as the sentence the validator
        # wrote, rather than as a stack trace on the caller's side.
        try:
            # The checks above are what make these casts true. Pydantic would refuse a
            # wrong value too, but as a validation error rather than as the sentence a
            # caller can act on — so the checking happens here, and this is how that
            # gets said to the type checker.
            payload = ChartPayload(
                chart=cast(ChartKind, chart),
                data=data,
                x_key=x_key,
                series=series,
                title=title,
                icon=icon,
                max=max,
                unit=unit,
                axes=cast(ChartAxes, axes),
                colors=colors or [],
                unfilled=unfilled,
                thresholds=cast(list[ChartThreshold], thresholds or []),
            )
        except (TypeError, ValueError) as exc:
            return f"Not added: {exc}"
        return await add(payload, x, y, w, h, description=description)
