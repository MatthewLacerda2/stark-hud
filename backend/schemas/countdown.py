"""What a countdown shows: things that are going to happen, and when.

Its own module for the reason the chart, the gantt and the media widget have
one — and, this time, because ``schemas.payloads`` had reached the house's line
ceiling. That limit fires on the sum rather than on any one change, and each
time it has fired there was a real seam underneath it. This is one: an entry
that now carries a rule about its own two ends is a type with behaviour, not one
more block of fields.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from schemas.icon import Icon
from schemas.spans import refuse_bad_span


class Countdown(BaseModel):
    """One thing that is going to happen, is happening, or just did.

    Two datetimes and a name. Deliberately no "remaining" field: that is a
    reading of the clock against these, and the browser is the only part of this
    board that has a clock — see ``CountdownPayload``.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    # A name from the icon set, a path to a picture, or SVG markup, drawn beside
    # the title. A picture is served by the id of the widget holding it.
    icon: Icon | None = None
    start: datetime
    # Left out, the thing is a moment rather than a window: it has a start and
    # is over as soon as it has begun.
    end: datetime | None = None

    @model_validator(mode="after")
    def _ends_after_it_starts(self) -> "Countdown":
        """Refuse a pair of instants that do not make a span, in a sentence.

        Here rather than in the tool that writes it, because a countdown is
        written over the API as well as through MCP and only one of those paths
        ever checked. The tool used to compare the two ends one line *after* its
        own ``except`` closed, so a start naming a timezone and an end not
        naming one escaped as an uncaught ``TypeError`` — a crash, for what is a
        typo in one of two fields.
        """
        refuse_bad_span(self.title, self.start, self.end)
        return self


class CountdownPayload(BaseModel):
    """How long until the next few things, stacked oldest deadline first.

    Nothing is ever written to this after it is set, for the reason a clock is
    never written to: the browser already knows what time it is, and a countdown
    fed over the socket would be one write a second forever and would freeze the
    moment its writer stopped. So this carries the datetimes — facts a browser
    cannot know — and the browser works out the reading.

    The order is not stored either, because it changes on its own as the clock
    passes each start and each end. What is happening comes before what is still
    to happen, which comes before what is over; the browser sorts on every tick.

    An entry stops being drawn twelve hours after it ends, but stays in the
    payload: this is a record somebody wrote, and dropping out is a reading of
    the clock against it like everything else here.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["countdown"] = "countdown"
    title: str | None = None
    icon: Icon | None = None
    items: list[Countdown] = []
    empty: str | None = None
