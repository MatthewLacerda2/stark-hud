"""Board item request/response schemas.

Every item carries a payload discriminated by ``kind``, so a chart can never be
validated as a note and the frontend can switch on one field.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ChartKind = Literal["line", "bar", "pie", "area"]
NotifyLevel = Literal["info", "success", "warn", "error"]


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
    """

    kind: Literal["chart"] = "chart"
    chart: ChartKind
    data: list[dict[str, float | int | str]]
    x_key: str
    series: list[str]
    title: str | None = None


class NotificationPayload(_Payload):
    """An announcement that stays on the board until dismissed."""

    kind: Literal["notification"] = "notification"
    message: str
    level: NotifyLevel = "info"
    source: str | None = None


Payload = Annotated[
    NotePayload
    | TextPayload
    | BoxPayload
    | ImagePayload
    | VideoPayload
    | ChartPayload
    | NotificationPayload,
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
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    w: int | None = Field(default=None, ge=1)
    h: int | None = Field(default=None, ge=1)
    parent_id: str | None = None
    pinned: bool = False


class ItemUpdate(BaseModel):
    """Partial update. Any field left as ``None`` is untouched."""

    payload: Payload | None = None
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    w: int | None = Field(default=None, ge=1)
    h: int | None = Field(default=None, ge=1)
    parent_id: str | None = None
    pinned: bool | None = None


class ItemRead(BaseModel):
    """An item as broadcast to every client."""

    id: str
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


class BoardStatus(BaseModel):
    """Occupancy summary, so a caller can look before it leaps."""

    cols: int
    rows: int
    cells_total: int
    cells_used: int
    cells_free: int
    item_count: int
    largest_free_rect: Placement | None
