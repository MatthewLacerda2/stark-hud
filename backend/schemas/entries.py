"""One line to add to a widget that keeps its lines rather than recomputing them.

Almost every widget on this board is written whole: whoever has the numbers
sends all of them. Two are not. A list somebody keeps and a countdown stack are
built up an entry at a time, often by sessions that never saw the other entries,
so rewriting the payload to add one would mean knowing every entry and losing
the ones you did not.

This is the shape of that one entry, for both of them. One model rather than two
because the route and the tool are one route and one tool: the caller names a
widget and a line, and which fields mean anything is decided by what the widget
is — ``start`` on a list, or a colour on a countdown, is a refusal with a
sentence rather than a field silently dropped. See ``services.entries``.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from schemas.colour import Colour
from schemas.icon import Icon


class EntryCreate(BaseModel):
    """A line for a list, or a thing for a countdown stack."""

    model_config = ConfigDict(extra="forbid")

    title: str
    # A name from the icon set, a path to a picture on this machine, or SVG
    # markup. Both kinds of entry take one.
    icon: Icon | None = None

    # A list entry's second, fainter line, and the colours for this line's own
    # parts. Each beats the widget-wide colour; left out, the part takes
    # whatever the list gives it.
    body: str | None = None
    title_color: Colour | None = None
    body_color: Colour | None = None
    icon_color: Colour | None = None

    # A countdown entry's two ends. ``start`` is what makes it one: when it
    # begins, and when it is over. Leave ``end`` out for a moment rather than a
    # window. Nothing ever writes how long is left — that is a reading of the
    # clock, and the browser holds the only one.
    start: datetime | None = None
    end: datetime | None = None
