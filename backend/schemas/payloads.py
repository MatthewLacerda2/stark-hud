"""What a widget shows.

Each payload is discriminated by ``kind``, so a chart can never be validated
as a note and the frontend can switch on one field. What a widget *is* —
where it sits, what it is made of, the note left on it — lives in
``schemas.board`` instead.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.chart import ChartAxes, ChartKind, ChartPayload, ChartThreshold
from schemas.colour import Colour
from schemas.icon import Icon
from schemas.media import MediaPayload, MediaTrack


class _Payload(BaseModel):
    """Base for every item payload; unknown keys are a client bug, not a default."""

    model_config = ConfigDict(extra="forbid")


class NotePayload(_Payload):
    """A sticky note: short body text on a tinted card."""

    kind: Literal["note"] = "note"
    text: str
    color: Colour | None = None


class TextPayload(_Payload):
    """Free-standing text with no card around it."""

    kind: Literal["text"] = "text"
    text: str
    size: Literal["sm", "md", "lg", "xl"] = "md"


class BoxPayload(_Payload):
    """A frame drawn on the board. Decoration, not a container.

    Holding widgets is a group's job — see ``GroupPayload`` — and ``parent_id``
    means membership of one. A box is a line around a region of the board and
    nothing more.
    """

    kind: Literal["box"] = "box"
    label: str | None = None
    fill: Colour | None = None
    stroke: Colour | None = None


class ListEntry(BaseModel):
    """One line of a list, when a bare string is not enough for it.

    Most entries are strings — something printed them and they are rewritten
    whole every few seconds — so this is the other case: a line a person put
    there on purpose, which may want a second line under it and a picture
    beside it.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    body: str | None = None
    # A name from the icon set, a path to a picture on this machine, or SVG
    # markup. A picture is served by the id of the widget holding it, never by
    # its path; markup is sanitised on the way in and stored sanitised.
    icon: Icon | None = None
    # This line's own colours, one per part. Each beats the widget-wide colour
    # for that part; left out, the part takes whatever the widget gives it, so
    # an entry that does not care still says nothing.
    title_color: Colour | None = None
    body_color: Colour | None = None
    icon_color: Colour | None = None


class ListPayload(_Payload):
    """A heading and the things under it.

    Its own kind rather than a note with newlines in it: a title and its entries
    are different weights and sizes, and joining them into one string throws
    that away.

    Every part can be coloured, and the rule is one sentence: an entry's own
    colour wins, then the widget-wide one — ``title_color`` for the heading and
    the icon beside it, ``item_color`` for anything inside an entry — and then
    the widget's own colour, which is what a list that names none of them gets.
    """

    kind: Literal["list"] = "list"
    title: str | None = None
    # A name from the icon set, a path to a picture, or SVG markup, drawn beside
    # the heading. A picture is served by this item's id, never by its path.
    icon: Icon | None = None
    # A line is a string or a ListEntry, and the two may be mixed. Strings stay
    # because that is what a script prints: the panels on this board are fed by
    # `tools/agent.py`, and making them build objects would buy nothing.
    items: list[str | ListEntry] = []
    empty: str | None = None
    # The widget-wide colours: the heading, the icon beside it, and every entry
    # that named no colour of its own. Any of them left out falls back to the
    # widget's own colour, so a plain list still needs no colours at all.
    title_color: Colour | None = None
    icon_color: Colour | None = None
    item_color: Colour | None = None


class ImagePayload(_Payload):
    """An image read from a local path and served back by this API."""

    kind: Literal["image"] = "image"
    path: str
    alt: str | None = None


class VideoPayload(_Payload):
    """A video read from a local path and served back by this API.

    One file, played once, with no idea what comes after it. A queue of them —
    audio as well as video, driven from a session rather than from the screen —
    is the ``media`` widget in ``schemas.media`` instead.
    """

    kind: Literal["video"] = "video"
    path: str
    autoplay: bool = True
    loop: bool = False
    muted: bool = True


class InboxPayload(_Payload):
    """Where notifications are shown.

    One widget holds all of them, the way a phone's shade does. Its height decides
    how many are visible at once and its width how much of each line fits;
    neither is configured, they are just consequences of the size it was given.
    """

    kind: Literal["inbox"] = "inbox"
    title: str | None = None


class FeedEntry(BaseModel):
    """One line in a feed.

    Shaped like a notification minus the parts a feed does not have: no level,
    because nothing here is an alert, and no icon, because `source` already says
    where the line came from and a column repeating that only steals width.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    source: str | None = None
    at: datetime | None = None


class FeedPayload(_Payload):
    """A list of things that happened, newest first.

    Read like the inbox — same line, same rhythm — but it is content someone
    polled rather than announcements pushed at us, so it lives in its own
    widget and is replaced whole on every refresh.
    """

    kind: Literal["feed"] = "feed"
    title: str | None = None
    # A name from the icon set, a path to a picture, or SVG markup, drawn beside
    # the heading. A picture is served by this item's id, never by its path.
    icon: Icon | None = None
    entries: list[FeedEntry] = []
    empty: str | None = None


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


class CountdownPayload(_Payload):
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

    kind: Literal["countdown"] = "countdown"
    title: str | None = None
    icon: Icon | None = None
    items: list[Countdown] = []
    empty: str | None = None


class GroupPayload(_Payload):
    """A widget that holds widgets.

    Membership is ``parent_id`` on the widgets themselves, so a group is an edge
    rather than a place: nothing moves into it and nothing is laid out inside it.

    It has two states, and they trade room with each other. **Open**, the group
    occupies nothing and its widgets sit on the board exactly where they always
    did. **Closed**, the widgets come off the board and the group takes their
    place, drawn as the icons of what is inside stacked like sleeves on a shelf
    — three visible and a fourth behind them, blurred, whether it holds five or
    twenty. What that says is what kind of things are in here and that there are
    several, which is all anybody across a room can use.

    A closed group is a fold. A group is also what a page was trying to be, and
    the reason pages are gone: a page was an integer with no name and no way to
    be empty, and this is a widget you can point at.

    Nesting stops here: a group holds widgets, never other groups. Not because a
    tree is hard to build but because a tree is hard to hold in your head, and no
    board we want needs the second level.
    """

    kind: Literal["group"] = "group"
    open: bool = True


class ClockPayload(_Payload):
    """The time now, with the date under it when the widget is tall enough.

    Nothing is ever written to it. The browser already knows what time it is,
    and a clock fed over the socket would stop the moment its writer did.
    """

    kind: Literal["clock"] = "clock"


Payload = Annotated[
    NotePayload
    | TextPayload
    | ListPayload
    | BoxPayload
    | ImagePayload
    | VideoPayload
    | MediaPayload
    | ChartPayload
    | InboxPayload
    | ClockPayload
    | FeedPayload
    | GroupPayload
    | CountdownPayload,
    Field(discriminator="kind"),
]

# The media widget and the chart each live in their own module — one is a queue,
# a transport and a report, the other is five kinds, four axis settings and a
# gauge that is not a series at all — and both are named here because this is
# where every layer already looks for a payload.
__all__ = [
    "BoxPayload",
    "ChartAxes",
    "ChartKind",
    "ChartPayload",
    "ChartThreshold",
    "ClockPayload",
    "Countdown",
    "CountdownPayload",
    "FeedEntry",
    "FeedPayload",
    "GroupPayload",
    "ImagePayload",
    "InboxPayload",
    "ListEntry",
    "ListPayload",
    "MediaPayload",
    "MediaTrack",
    "NotePayload",
    "Payload",
    "TextPayload",
    "VideoPayload",
]
