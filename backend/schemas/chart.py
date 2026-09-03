"""What a chart shows.

Its own module for the reason the media widget has one: this is not one more
block of fields. A chart is five kinds, four axis settings, thresholds that turn
a mark when a value passes them, and a radial that is not a series at all but a
gauge — and the description of that vocabulary is most of what anyone reads
before drawing one. `hud_mcp/charts.py` is the tool that matches it.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from schemas.colour import Colour
from schemas.icon import Icon

ChartKind = Literal["line", "bar", "pie", "area", "radial"]

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

    A ``radial`` chart is the odd one out: it reads the first row only and draws
    it as an arc of a full ring whose ceiling is ``max``. It is a gauge, not a
    series. The ring carries the proportion, so the middle is an identity —
    ``icon`` and ``title`` — with ``data[0][x_key]`` under it for when a number
    is genuinely wanted. Each of the three is drawn only if it is there.

    ``unit`` does nothing on a radial: there is no longer a bare number for it
    to sit against, and whatever wrote ``data[0][x_key]`` already spelled the
    reading out the way it wants it read.
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
    # Drawn at the origin on a cartesian chart, stacked above ``icon`` and
    # anchored to that corner, so a longer one grows upward into space the axes
    # already frame rather than pushing the plot down. A gauge draws it in the
    # middle of its ring instead. Either way it costs no height.
    title: str | None = None
    # Where a chart says what it is. A gauge draws it beside its title in the
    # middle of its ring; every other chart draws it at the origin, in the
    # corner the axes already frame, where it costs no height. The same three
    # forms an icon has anywhere else on the board.
    icon: Icon | None = None
    # A ceiling for the value axis. Left out, the axis fits the data, which is
    # right for a count and wrong for a percentage: 21% would draw nearly full.
    # A radial always has one, defaulting to 100.
    max: float | None = None
    # What the numbers are counted in. A radial ignores it — see the note above
    # — and it is the only chart that ever drew it, so nothing draws it today.
    # Kept because it is a published field and a caller may still be sending it.
    unit: str | None = None
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
