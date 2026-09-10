"""What a gantt shows: named rows of spans, drawn against the clock.

Its own module for the reason the chart and the media widget have one — a
payload made of two further models is not one more block of fields, and
``schemas.payloads`` is at the house limit. ``hud_mcp/gantts.py`` is the tool
that matches it.

Nothing here is a duration and nothing here is an offset. The board carries the
instants; the browser owns the only clock on this board and works out the
geometry on every tick — see ``GanttPayload``.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from schemas.colour import Colour
from schemas.icon import Icon


class GanttBar(BaseModel):
    """One stretch of time, with a name on it.

    Not a ``Countdown``, though it is nearly one. A countdown entry is a
    *moment* that may happen to have an end; a bar is a *span* and cannot be
    drawn without one, because width is the only thing here that carries
    duration. A countdown entry also has an icon, and a bar has nowhere to put
    one: what fits inside a bar is a word, or nothing.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    start: datetime
    end: datetime
    # Left out, the bar takes its row's colour, which is the board's own palette
    # cycled one row at a time. An eight-digit hex carries its own alpha, and a
    # colour that says how see-through it is is not made see-through twice.
    color: Colour | None = None

    @model_validator(mode="after")
    def _has_width(self) -> "GanttBar":
        """Refuse a bar that could not be drawn, in a sentence naming which one."""
        # Both aware or both naive, or the comparison below raises TypeError and
        # the caller gets a 500 for what is a typo in one of two fields.
        if (self.start.tzinfo is None) != (self.end.tzinfo is None):
            raise ValueError(
                f"{self.title!r} names a timezone on one end and not the other; "
                f"give both or neither"
            )
        if self.end <= self.start:
            raise ValueError(f"{self.title!r} would end at or before it starts")
        return self


class GanttRow(BaseModel):
    """A named track and the bars sitting on it.

    The name is what makes two bars at the same time readable as two different
    things rather than as one thing drawn twice, so it is required. Bars may
    overlap inside a row — that is a row doing two things at once, and saying
    so is the whole point of the widget.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    bars: list[GanttBar] = []


class GanttPayload(BaseModel):
    """The next stretch of time, as rows of bars.

    Nothing is ever written to this after it is set, for the reason a clock and
    a countdown are never written to: a payload carrying "45 minutes from now"
    freezes the moment its writer stops. This carries the instants — facts a
    browser cannot know — and the browser reads them against its own clock on
    every tick. An evening dictated at 18:00 plays itself out until midnight
    with no further writes, no agent and no socket traffic.

    The window is not stored either, and for the same reason: it is the smallest
    step that covers the next few bars, which changes on its own as the clock
    passes each of them. The left edge is always *now*, so nothing behind it is
    drawn and a bar already running clips at that edge — which reads correctly
    as *this has started*. See ``lib/gantt.ts`` for the ladder of steps and the
    five-minute floor.

    What this deliberately does not carry is anything the word *gantt* means
    elsewhere: no dependencies, no milestones, no percent complete, no critical
    path. It draws spans and says nothing about the relationships between them.
    """

    # Set here rather than inherited, like the chart and the media widget: this
    # module cannot import the base in ``payloads`` without a cycle, since that
    # module imports this one.
    model_config = ConfigDict(extra="forbid")

    kind: Literal["gantt"] = "gantt"
    title: str | None = None
    # A name from the icon set, a path to a picture, or SVG markup, drawn beside
    # the heading. A picture is served by this item's id, never by its path.
    icon: Icon | None = None
    rows: list[GanttRow] = []
    empty: str | None = None
