"""What a chart shows.

Its own module for the reason the media widget has one: this is not one more
block of fields. A chart is six kinds, four axis settings, thresholds that turn
a mark when a value passes them, and two polar ones — a radial that is a gauge
rather than a series, and a radar that is a shape rather than a reading. The
description of that vocabulary is most of what anyone reads before drawing one.
`hud_mcp/charts.py` is the tool that matches it.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from schemas.colour import Colour
from schemas.icon import Icon

ChartKind = Literal["line", "bar", "pie", "area", "radial", "radar"]

# The most rings one gauge draws. Kept beside the kind rather than in the
# widget, because it is the number a caller is refused against — the browser
# has its own copy for laying them out and neither is allowed to be the only
# one that knows.
MAX_RINGS = 3

ChartAxes = Literal["both", "x", "y", "none"]


class ChartThreshold(BaseModel):
    """A value a mark changes colour above.

    The board's charts are all one tone on purpose, so nothing on the wall
    shouts. This is how something earns the right to: a mark above ``at`` stops
    being that tone and turns, and colour reads as a signal rather than as
    decoration.

    ``at`` is in the units of the plotted value. A gauge that plots a percentage
    is crossed at ``77``, not at the twelve gigabytes that percentage stands for.
    """

    model_config = ConfigDict(extra="forbid")

    at: float
    color: Colour


class ChartPayload(BaseModel):
    """A chart drawn from data supplied inline.

    The board never fetches or polls: whoever has the numbers sends them.
    Updating a chart means writing the item again with new ``data``.

    A ``radial`` chart is the odd one out: each row is a ring, drawn as an arc
    of a full circle whose ceiling is ``max``. It is a gauge, not a series.

    Up to three rings, concentric and sharing their edges, first row outermost —
    in the order they arrive, so a ring does not change places when a number
    moves. Three readings that belong together used to cost three widgets and
    half the board's width; a ring does not need the middle of its circle, so
    the next one goes inside it. Three is the ceiling because four is a target,
    five is a pattern, and a widget full of concentric circles stops being
    readings and becomes a texture. A fourth row is refused rather than dropped
    — see ``_rings_that_can_be_read``.

    The ring carries the proportion, so the middle is an identity — ``icon`` and
    ``title`` — with ``data[0][x_key]`` under it for when a number is genuinely
    wanted. Each of the three is drawn only if it is there.

    With more than one ring that spelled-out reading is not drawn: three
    sentences do not fit in a hole that shrank to make room for the rings, and
    each ring already carries its own proportion. The title then names the set
    rather than a reading — "Machine" rather than "RAM".

    One ``max`` and one ``unfilled`` for the whole widget. If three rings need
    three ceilings, send percentages: a ceiling per row is a field whose only
    purpose is to make an unreadable widget possible.

    ``unit`` does nothing on a radial: there is no longer a bare number for it
    to sit against, and whatever wrote ``data[0][x_key]`` already spelled the
    reading out the way it wants it read.

    A ``radar`` is the other polar one, and it is a shape rather than a reading.
    One row per spoke and one series, drawn as a polygon inside a grid that stays
    visible — so a machine at idle is a small polygon in a reticle rather than an
    empty widget. It answers "how much, and is it one of them or all of them" in
    a glance, which is what a screen across a room can be asked. The rows go
    round the ring in the order they arrive, so whoever sends them decides which
    spoke sits next to which; ``max`` is the ceiling the polygon is drawn
    against, and without one the widest value fills the grid.
    """

    # Set here rather than inherited: this module cannot import the base in
    # ``payloads`` without a cycle, since that module imports this one. The
    # media widget, the other payload with a module of its own, does the same.
    model_config = ConfigDict(extra="forbid")

    kind: Literal["chart"] = "chart"
    chart: ChartKind
    data: list[dict[str, float | int | str]]
    x_key: str
    series: list[str]
    # Drawn in the top-left corner on a cartesian chart, stacked under ``icon``
    # and anchored there, so a longer one grows downward over the plot rather
    # than pushing it anywhere. A gauge draws it in the middle of its ring
    # instead. Either way it costs no height.
    title: str | None = None
    # Where a chart says what it is. A gauge draws it beside its title in the
    # middle of its ring; every other chart draws it in the top-left corner,
    # where a chart has been labelled since long before this one and where the
    # eye starts. It costs no height either way. The same three forms an icon
    # has anywhere else on the board.
    icon: Icon | None = None
    # A ceiling for the value axis. Left out, the axis fits the data, which is
    # right for a count and wrong for a percentage: 21% would draw nearly full.
    # A radar reads it too — it is what holds the polygon to a fixed ring. A
    # radial always has one, defaulting to 100.
    max: float | None = None
    # What the numbers are counted in. A radial ignores it — see the note above
    # — and it is the only chart that ever drew it, so nothing draws it today.
    # Kept because it is a published field and a caller may still be sending it.
    unit: str | None = None
    # Cartesian only. A pie, a radial and a radar have no axes to draw.
    axes: ChartAxes = "both"
    # A gauge's ring behind the value. Left alone it is white kept see-through,
    # which is what a ring on a dark video wants; it is a field because finding
    # the right amount of white took more than one try, and a constant costs a
    # rebuild each time. Ignored by every chart that is not a gauge.
    unfilled: Colour | None = None
    # One CSS colour per series, cycled if shorter. Any colour the browser
    # understands, so `var(--chart-2)` picks a theme token and anything else is
    # literal. Empty means the default palette.
    colors: list[Colour] = []
    # Values above which a mark turns. The highest one a value clears wins, so
    # an "attention" and an "alarm" level can sit on the same chart; a value
    # under all of them keeps the colour it would have had anyway. Bar and
    # radial only: a bar decides one bar at a time and a gauge decides on its
    # single value, while a pie and a line already give every series a colour of
    # its own and a threshold on top of that would fight what the colour means.
    # Empty is the default, so a chart that names none looks exactly as it did.
    thresholds: list[ChartThreshold] = []

    @model_validator(mode="after")
    def _rings_that_can_be_read(self) -> "ChartPayload":
        """Refuse a radial with more rows than it can draw as rings.

        Refused rather than truncated, because a widget that silently shows
        three of four numbers is worse than one that does not appear: the
        missing one is invisible from the sofa and the caller is never told. A
        session that meant four readings wanted a second widget, and this is
        where it finds that out.
        """
        if self.chart == "radial" and len(self.data) > MAX_RINGS:
            raise ValueError(
                f"a radial draws at most {MAX_RINGS} rings and this one has "
                f"{len(self.data)} rows; send fewer, or use a second widget"
            )
        return self
