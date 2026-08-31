"""Board item request/response schemas.

Every item carries a payload discriminated by ``kind``, so a chart can never be
validated as a note and the frontend can switch on one field.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.notifications import Notification

ChartKind = Literal["line", "bar", "pie", "area", "radial"]


class _Payload(BaseModel):
    """Base for every item payload; unknown keys are a client bug, not a default."""

    model_config = ConfigDict(extra="forbid")


class NotePayload(_Payload):
    """A sticky note: short body text on a tinted card."""

    kind: Literal["note"] = "note"
    text: str
    color: str | None = None


class TextPayload(_Payload):
    """Free-standing text with no card around it."""

    kind: Literal["text"] = "text"
    text: str
    size: Literal["sm", "md", "lg", "xl"] = "md"


class BoxPayload(_Payload):
    """A container. Other items may name it as their ``parent_id``."""

    kind: Literal["box"] = "box"
    label: str | None = None
    fill: str | None = None
    stroke: str | None = None


class ListPayload(_Payload):
    """A heading and the things under it.

    Its own kind rather than a note with newlines in it: a title and its entries
    are different weights and sizes, and joining them into one string throws
    that away.
    """

    kind: Literal["list"] = "list"
    title: str | None = None
    items: list[str] = []
    empty: str | None = None


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
    colors: list[str] = []


class InboxPayload(_Payload):
    """Where notifications are shown.

    One tile holds all of them, the way a phone's shade does. Its height decides
    how many are visible at once and its width how much of each line fits;
    neither is configured, they are just consequences of the size it was given.
    """

    kind: Literal["inbox"] = "inbox"
    title: str | None = None


Payload = Annotated[
    NotePayload
    | TextPayload
    | ListPayload
    | BoxPayload
    | ImagePayload
    | VideoPayload
    | ChartPayload
    | InboxPayload,
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
    default to a size that suits the kind.
    """

    payload: Payload
    key: str | None = None
    opacity: float | None = Field(default=None, ge=0, le=1)
    color: str | None = None
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
    opacity: float | None = Field(default=None, ge=0, le=1)
    color: str | None = None
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
    # The three things a tile can be told about itself. None means the default
    # for its kind: a chart is barely there, prose needs something behind it.
    opacity: float | None = None
    # The colour of the tile's text. The background is its kind's, at `opacity`.
    color: str | None = None
    # Multiplies the text sizes inside this tile. The type still scales with the
    # tile, this just moves the whole range.
    scale: float | None = None
    payload: Payload
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


class BoardStatus(BaseModel):
    """Occupancy summary, so a caller can look before it leaps."""

    cols: int
    rows: int
    cells_total: int
    cells_used: int
    cells_free: int
    item_count: int
    largest_free_rect: Placement | None
