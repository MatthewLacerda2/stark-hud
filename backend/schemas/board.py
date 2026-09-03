"""What a widget is: where it sits, how it looks, and the note left on it.

What a widget *shows* lives in ``schemas.payloads`` and is re-exported here,
because ``schemas.board`` is the name every layer already imports from.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.colour import Colour
from schemas.media import MEDIA_ACTIONS, MediaAction, Playback, PlaybackReport
from schemas.notifications import Notification
from schemas.payloads import (
    BoxPayload,
    ChartAxes,
    ChartKind,
    ChartPayload,
    ClockPayload,
    FeedEntry,
    FeedPayload,
    ImagePayload,
    InboxPayload,
    ListEntry,
    ListPayload,
    MediaPayload,
    MediaTrack,
    NotePayload,
    Payload,
    TextPayload,
    VideoPayload,
)

__all__ = [
    "BoxPayload",
    "ChartAxes",
    "ChartKind",
    "ChartPayload",
    "ClockPayload",
    "FeedEntry",
    "FeedPayload",
    "ImagePayload",
    "InboxPayload",
    "ListEntry",
    "ListPayload",
    "MEDIA_ACTIONS",
    "MediaAction",
    "MediaPayload",
    "MediaTrack",
    "NotePayload",
    "Payload",
    "Playback",
    "PlaybackReport",
    "TextPayload",
    "VideoPayload",
]


# The smallest a widget may be, in cells. A cell is roughly 60px on the 1080p
# television this is read from, so a quarter of one is about 15px — the point
# below which a widget stops being small and becomes invisible while still
# refusing to let anything overlap it. Zero is not the floor for that reason.
MIN_SIZE = 0.25


class Placement(BaseModel):
    """Where an item sits, in columns and rows. Never pixels.

    Fractional: the board is a 32-by-18 space rather than 576 slots, so a
    widget sits where it was put. Whole numbers still mean exactly what they
    always meant, which is why every call written before this went on working.
    """

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    w: float = Field(ge=MIN_SIZE)
    h: float = Field(ge=MIN_SIZE)


class ItemCreate(BaseModel):
    """Payload to add an item.

    Omit ``x``/``y`` to let the auto-placer choose a free slot. ``w``/``h``
    default to a size that suits the kind. Omit ``page`` and it lands on the one
    being shown, which is the only page anybody can see.
    """

    payload: Payload
    key: str | None = None
    description: str | None = None
    page: int | None = Field(default=None, ge=0)
    opacity: float | None = Field(default=None, ge=0, le=1)
    color: Colour | None = None
    background: Colour | None = None
    border: Colour | None = None
    scale: float | None = Field(default=None, ge=0.25, le=4)
    x: float | None = Field(default=None, ge=0)
    y: float | None = Field(default=None, ge=0)
    w: float | None = Field(default=None, ge=MIN_SIZE)
    h: float | None = Field(default=None, ge=MIN_SIZE)
    parent_id: str | None = None
    pinned: bool = False


class ItemUpdate(BaseModel):
    """Partial update. Any field left as ``None`` is untouched."""

    payload: Payload | None = None
    key: str | None = None
    # ``None`` leaves the note alone like every other field here, so an empty
    # string is how it is cleared. Without that there would be no way back from
    # a wrong note, and adding a second "unset" sentinel for one field would
    # cost more than the rule does.
    description: str | None = None
    page: int | None = Field(default=None, ge=0)
    opacity: float | None = Field(default=None, ge=0, le=1)
    color: Colour | None = None
    background: Colour | None = None
    border: Colour | None = None
    scale: float | None = Field(default=None, ge=0.25, le=4)
    x: float | None = Field(default=None, ge=0)
    y: float | None = Field(default=None, ge=0)
    w: float | None = Field(default=None, ge=MIN_SIZE)
    h: float | None = Field(default=None, ge=MIN_SIZE)
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
    # A note for whoever drives the board next, never drawn on the TV. It says
    # what a widget is for, what it is waiting on, what its number means — the
    # things a later session cannot recover by looking. It lives here beside
    # ``x`` and ``y`` rather than inside the payload because a panel's payload is
    # rewritten whole every few seconds, which would erase it on the next pass.
    description: str | None = None
    # The three things a widget can be told about itself. None means the default
    # for its kind: a chart is barely there, prose needs something behind it.
    opacity: float | None = None
    # The colour of the widget's text.
    color: str | None = None
    # What the widget's background is made of, shown at `opacity`. None means
    # the card colour every other widget uses, which is the case needing no
    # thought; this is for the one widget that should not look like the rest.
    background: str | None = None
    # A line around the widget, at whatever colour is given. None is no line,
    # which is what almost every widget wants: a board of outlined rectangles is
    # a form, not a view. This is the one style that ignores `opacity` — the
    # point of it is a clear edge on a widget whose background has been turned
    # right down, so fading it with the thing it is drawn around would defeat
    # it. A colour carrying its own alpha is how you ask for a faint one.
    border: str | None = None
    # Multiplies the text sizes inside this widget. The type still scales with the
    # widget, this just moves the whole range.
    scale: float | None = None
    payload: Payload
    # What the browser says this widget is actually doing, for the one widget
    # that can fail on its own: a media file may be missing, or in a codec the
    # browser will not take, and without this that would be invisible from
    # anywhere but the sofa. It lives here beside ``description`` rather than in
    # the payload for the same reason that does — a payload is rewritten whole
    # by whoever owns it, and this is not theirs to overwrite.
    playback: Playback | None = None
    # Which screen this widget is on. Pages exist because the grid never
    # scrolls: a second screenful is the only way to have more than fits, and
    # the board shows exactly one at a time.
    page: int = 0
    x: float
    y: float
    w: float
    h: float
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
    cells_total: float
    cells_used: float
    cells_free: float
    item_count: int
    largest_free_rect: Placement | None
