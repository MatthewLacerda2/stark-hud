"""Board item request/response schemas.

Every item carries a payload discriminated by ``kind``, so a chart can never be
validated as a note and the frontend can switch on one field.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.colour import Colour
from schemas.notifications import ICONS, Notification

ChartKind = Literal["line", "bar", "pie", "area", "radial"]


def check_icon(value: str | None) -> str | None:
    """Refuse an icon that is neither a name from the set nor a path to a picture.

    The same vocabulary a notification's icon has: a widget may point at a file
    on this machine instead of picking a glyph. Refused rather than quietly
    dropped, so a typo is visible to whoever wrote it. Whether the file is still
    there is a separate question, answered when the picture is asked for.
    """
    if value is not None and value not in ICONS and not value.startswith("/"):
        raise ValueError(
            f"{value!r} is not an icon: pass one of {', '.join(sorted(ICONS))}, "
            "or an absolute path to an image file"
        )
    return value


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
    # A name from the icon set, or a path to a picture on this machine. A
    # picture is served by the id of the widget holding it, never by its path.
    icon: str | None = None

    @field_validator("icon")
    @classmethod
    def _known_icon(cls, value: str | None) -> str | None:
        return check_icon(value)


class ListPayload(_Payload):
    """A heading and the things under it.

    Its own kind rather than a note with newlines in it: a title and its entries
    are different weights and sizes, and joining them into one string throws
    that away.
    """

    kind: Literal["list"] = "list"
    title: str | None = None
    # A line is a string or a ListEntry, and the two may be mixed. Strings stay
    # because that is what a script prints: the panels on this board are fed by
    # `tools/agent.py`, and making them build objects would buy nothing.
    items: list[str | ListEntry] = []
    empty: str | None = None
    # A heading and its entries may be coloured apart. Either left out falls
    # back to the widget's own colour, so a plain list still needs no colours.
    title_color: Colour | None = None
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

    A ``radial`` chart is the odd one out: it reads the first row only, draws it
    as an arc of ``max``, and prints the value in the middle. It is a gauge, not
    a series.
    """

    kind: Literal["chart"] = "chart"
    chart: ChartKind
    data: list[dict[str, float | int | str]]
    x_key: str
    series: list[str]
    title: str | None = None
    # A ceiling for the value axis. Left out, the axis fits the data, which is
    # right for a count and wrong for a percentage: 21% would draw nearly full.
    # A radial always has one, defaulting to 100.
    max: float | None = None
    unit: str | None = None
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
    # A name from the icon set, or a path to a picture, drawn beside the
    # heading. A picture is served by this item's id, never by its path.
    icon: str | None = None
    entries: list[FeedEntry] = []
    empty: str | None = None

    @field_validator("icon")
    @classmethod
    def _known_icon(cls, value: str | None) -> str | None:
        return check_icon(value)


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


class Placement(BaseModel):
    """Where an item sits, in grid cells. Never pixels."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(ge=1)
    h: int = Field(ge=1)


class ItemCreate(BaseModel):
    """Payload to add an item.

    Omit ``x``/``y`` to let the auto-placer choose a free slot. ``w``/``h``
    default to a size that suits the kind. Omit ``page`` and it lands on the one
    being shown, which is the only page anybody can see.
    """

    payload: Payload
    key: str | None = None
    page: int | None = Field(default=None, ge=0)
    opacity: float | None = Field(default=None, ge=0, le=1)
    color: Colour | None = None
    scale: float | None = Field(default=None, ge=0.25, le=4)
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    w: int | None = Field(default=None, ge=1)
    h: int | None = Field(default=None, ge=1)
    parent_id: str | None = None
    pinned: bool = False


class ItemUpdate(BaseModel):
    """Partial update. Any field left as ``None`` is untouched."""

    payload: Payload | None = None
    key: str | None = None
    page: int | None = Field(default=None, ge=0)
    opacity: float | None = Field(default=None, ge=0, le=1)
    color: Colour | None = None
    scale: float | None = Field(default=None, ge=0.25, le=4)
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    w: int | None = Field(default=None, ge=1)
    h: int | None = Field(default=None, ge=1)
    parent_id: str | None = None
    pinned: bool | None = None


class ItemRead(BaseModel):
    """An item as broadcast to every client."""

    id: str
    # A caller-supplied name for something it will write again — a panel that
    # updates rather than a one-off. Whoever writes it can find it later without
    # remembering an id, which is what lets a refresher survive losing its state
    # or being replaced by another process entirely.
    key: str | None = None
    # The three things a widget can be told about itself. None means the default
    # for its kind: a chart is barely there, prose needs something behind it.
    opacity: float | None = None
    # The colour of the widget's text. The background is its kind's, at `opacity`.
    color: str | None = None
    # Multiplies the text sizes inside this widget. The type still scales with the
    # widget, this just moves the whole range.
    scale: float | None = None
    payload: Payload
    # Which screen this widget is on. Pages exist because the grid never
    # scrolls: a second screenful is the only way to have more than fits, and
    # the board shows exactly one at a time.
    page: int = 0
    x: int
    y: int
    w: int
    h: int
    parent_id: str | None
    pinned: bool
    created_at: datetime


class Background(BaseModel):
    """A looping video behind the grid.

    Never has audio: this is wallpaper, and a board that makes noise on its own
    is a board nobody leaves running.
    """

    model_config = ConfigDict(extra="forbid")

    path: str
    blur: bool = False


class BoardSnapshot(BaseModel):
    """Everything a client needs on connect."""

    items: list[ItemRead]
    background: Background | None
    notifications: list[Notification]
    # The page being shown. One number for every client, so turning the page on
    # a laptop turns it on the TV, which has nothing to turn it with.
    page: int = 0


class BoardStatus(BaseModel):
    """Occupancy summary, so a caller can look before it leaps."""

    cols: int
    rows: int
    # Occupancy is per page: each page is its own grid of the same size.
    page: int
    pages: int
    cells_total: int
    cells_used: int
    cells_free: int
    item_count: int
    largest_free_rect: Placement | None
