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
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        description: str | None = None,
    ) -> str:
        """Draw a chart from data you supply inline.

        The board never fetches or polls: send the numbers. `chart` is line, bar,
        pie, area, radial or radar. `x_key` names the field on the x axis and
        `series` names the fields to plot. To update a chart, remove it and add
        it again.

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

        `unfilled` is the rest of a gauge's ring: the part the arc has not
        reached. Translucent white unless you say otherwise, and it is meant to
        stay translucent — the track is what makes the arc read as a proportion
        rather than as a lonely stripe, and a solid one turns the gauge into a
        dark disc with a bright edge on it. An eight-digit hex is the usual way
        to say how see-through: `#ffffff40` is a quarter, `#ffffff80` a half.
        Only a radial has a ring, so only a radial reads this.

        `at` is in the units of the plotted value, not of what the number means
        to a human. The memory gauge plots a percentage, so "above 12 GB of
        15.6" is `at: 77`, not `at: 12`.

        Only bar and radial read `thresholds`. A bar decides one bar at a time,
        so a single hot core turns while the rest stay as they were, and a gauge
        decides on its one value. A pie and a line chart already give every
        series a colour of its own — that is what those charts are for — so they
        ignore the field completely rather than half-honouring it.

        A radial is a gauge: each row of `data` is a ring, drawn as an arc of a
        circle whose ceiling is `max`, so always pass `max`. The ring is the
        message — it says the proportion from across the room.

        Up to three rings, concentric and touching, first row outermost. Use
        that instead of three gauges when three readings belong together: the
        board is finite and never scrolls, and three percentages used to cost
        half its width. Each ring takes its own colour from `colors` and its own
        `thresholds`, so one can turn while the others stay white. A fourth row
        is refused — that is a second widget.

        The middle of the rings is who the gauge is: `icon` and `title` side by
        side, with `data[0][x_key]` under them for when a number is genuinely
        wanted, the way "3.7 of 15.6 GB" is. With more than one ring that
        spelled-out reading is not drawn, so write a `title` that names the set
        rather than a reading — "Machine" rather than "RAM". Keep it to about
        six characters; a longer one is not refused, it just runs out of ring to
        sit in. `unit` does nothing on a radial, because there is no bare number
        for it to sit against.

        A radar is the other polar one, and it is a shape rather than a reading:
        one row per spoke, one series, drawn as a polygon inside a grid that
        stays visible so an idle machine is a small polygon in a reticle rather
        than an empty widget. Pass `max` — it is the ring the polygon is drawn
        against, and without one the largest value fills it whatever it is. Send
        the rows in the order you want them to go round; neighbouring spokes are
        what a viewer reads as one lobe, so put things that belong together next
        to each other. `axes` means nothing here, and neither does a second
        series: two polygons over one another are two shapes to disentangle,
        which is the opposite of what this chart is for.

        Every other chart says what it is in its top-left corner: `icon` at the
        top and `title` stacked under it, anchored there — a longer title grows
        downward over the plot rather than pushing it anywhere, so neither of
        them costs the chart any height. That is what lets a CPU widget be a
        slim strip of bars and still say it is the CPU. Pass either, both or
        neither; all four are meaningful.

        `icon` is a name from the notification icon set, an absolute path to a
        picture on this machine, or SVG markup — `<svg viewBox="0 0 24 24" ...>`
        with paths and shapes in it, which is how you draw something the icon
        set has no name for. It is sanitised on the way in, so anything that
        loads or runs is dropped. Paint it with `currentColor` and it takes the
        widget's colour.
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
