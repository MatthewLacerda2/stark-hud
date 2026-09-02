"""What a widget shows.

Each payload is discriminated by ``kind``, so a chart can never be validated
as a note and the frontend can switch on one field. What a widget *is* —
where it sits, what it is made of, the note left on it — lives in
``schemas.board`` instead.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.colour import Colour
from schemas.icon import Icon

ChartKind = Literal["line", "bar", "pie", "area", "radial"]

ChartAxes = Literal["both", "x", "y", "none"]


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
    """A container. Other items may name it as their ``parent_id``."""

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
    """A video read from a local path and served back by this API."""

    kind: Literal["video"] = "video"
    path: str
    autoplay: bool = True
    loop: bool = False
    muted: bool = True


class ChartPayload(_Payload):
    """A chart drawn from data supplied inline.

    The board never fetches or polls: whoever has the numbers sends them.
    Updating a chart means writing the item again with new ``data``.

    A ``radial`` chart is the odd one out: it reads the first row only and draws
    it as an arc of a full ring whose ceiling is ``max``. It is a gauge, not a
    series. The ring carries the proportion, so the middle is an identity —
    ``icon`` and ``title`` — with ``data[0][x_key]`` under it for when a number
    is genuinely wanted. Each of the three is drawn only if it is there, and
    ``title`` is drawn in the middle rather than in the widget's corner.

    ``unit`` does nothing on a radial: there is no longer a bare number for it
    to sit against, and whatever wrote ``data[0][x_key]`` already spelled the
    reading out the way it wants it read.
    """

    kind: Literal["chart"] = "chart"
    chart: ChartKind
    data: list[dict[str, float | int | str]]
    x_key: str
    series: list[str]
    title: str | None = None
    # Drawn beside the title in the middle of a gauge; nothing else uses it yet.
    # The same three forms an icon has anywhere else on the board.
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
    # One CSS colour per series, cycled if shorter. Any colour the browser
    # understands, so `var(--chart-2)` picks a theme token and anything else is
    # literal. Empty means the default palette.
    colors: list[Colour] = []


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
    | ChartPayload
    | InboxPayload
    | ClockPayload
    | FeedPayload,
    Field(discriminator="kind"),
]
