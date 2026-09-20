"""The board itself: the video behind the widgets, and the ink they are written in.

What a widget *is* lives in ``schemas.item`` and what a widget *shows* lives in
``schemas.payloads``. Both are re-exported here, because ``schemas.board`` is
the name every layer already imports from — and that is worth keeping even
though the models no longer all live in this file.

They stopped living here when this file reached the 350-line ceiling with a
fifth style field still to add. The cut is along the meaning the docstring
already claimed: a widget is one thing, the board that holds it is another.
"""

from pydantic import BaseModel, ConfigDict

from schemas.colour import Colour
from schemas.item import (
    DEFAULT_PAGE,
    MIN_SIZE,
    Arrangement,
    Change,
    ItemCreate,
    ItemRead,
    ItemUpdate,
    Placement,
)
from schemas.media import MEDIA_ACTIONS, MediaAction, Playback, PlaybackReport
from schemas.mesh import MeshPart, MeshWave, WaveMode, Wireframe
from schemas.notifications import Notification
from schemas.payloads import (
    Align,
    BoxPayload,
    CalendarPayload,
    ChartAxes,
    ChartKind,
    ChartPayload,
    ChartThreshold,
    ClockPayload,
    Countdown,
    CountdownPayload,
    FeedEntry,
    FeedPayload,
    FlowLink,
    FlowNode,
    FlowPayload,
    GanttBar,
    GanttPayload,
    GanttRow,
    GroupPayload,
    GroupState,
    IconSide,
    ImagePayload,
    InboxPayload,
    ListEntry,
    ListPayload,
    MediaPayload,
    MediaTrack,
    MeshPayload,
    NotePayload,
    Payload,
    ProgressPayload,
    TableColumn,
    TablePayload,
    TextPayload,
    TextSize,
)

__all__ = [
    "DEFAULT_PAGE",
    "MEDIA_ACTIONS",
    "MIN_SIZE",
    "Align",
    "Arrangement",
    "BoxPayload",
    "CalendarPayload",
    "Change",
    "ChartAxes",
    "ChartKind",
    "ChartPayload",
    "ChartThreshold",
    "ClockPayload",
    "Countdown",
    "CountdownPayload",
    "FeedEntry",
    "FeedPayload",
    "FlowLink",
    "FlowNode",
    "FlowPayload",
    "GanttBar",
    "GanttPayload",
    "GanttRow",
    "GroupPayload",
    "GroupState",
    "IconSide",
    "ImagePayload",
    "InboxPayload",
    "ItemCreate",
    "ItemRead",
    "ItemUpdate",
    "ListEntry",
    "ListPayload",
    "MediaAction",
    "MediaPayload",
    "MediaTrack",
    "MeshPart",
    "MeshPayload",
    "MeshWave",
    "NotePayload",
    "Payload",
    "Placement",
    "Playback",
    "PlaybackReport",
    "ProgressPayload",
    "TableColumn",
    "TablePayload",
    "TextPayload",
    "TextSize",
    "WaveMode",
    "Wireframe",
]


class Background(BaseModel):
    """A looping video behind the grid.

    Never has audio: this is wallpaper, and a board that makes noise on its own
    is a board nobody leaves running.
    """

    model_config = ConfigDict(extra="forbid")

    path: str
    blur: bool = False


class Ink(BaseModel):
    """The colour the board writes in, for every widget not given one of its own.

    White at 65% is the default and it is not arbitrary: the ink is meant to let
    the video behind it show through, which is what makes a readout look
    displayed rather than pasted on. It lives here as a setting because the right
    value depends on what is playing behind it — a bright background eats a
    translucent ink, and that is a thing to fix in a second, from the sofa, not
    in a rebuild.

    A widget told its own colour still gets exactly that: this is the default,
    never an override.
    """

    model_config = ConfigDict(extra="forbid")

    color: Colour


class BoardSnapshot(BaseModel):
    """Everything a client needs on connect."""

    items: list[ItemRead]
    # Which page the board is turned to. Every widget is sent, whatever page it
    # is on, and the page decides which of them the television draws — the same
    # rule the server keeps, so the two cannot disagree about what is up.
    showing: str
    background: Background | None
    ink: Ink | None
    notifications: list[Notification]


class BoardArranged(BaseModel):
    """The board whole, as the one event a rearrangement sends.

    Turning the page rides on this rather than on an event of its own, because
    it is the same thing from the television's side: the widgets on screen are
    replaced in a single frame. Sent whole so the TV cuts instead of dealing
    them out one at a time.
    """

    items: list[ItemRead]
    showing: str


class BoardStatus(BaseModel):
    """Occupancy summary of the page that is showing, so a caller can look
    before it leaps.

    Judged against one page: each page has the whole grid to itself, so a board
    carrying four of them reports the room on the one that is up.
    """

    # The page these numbers are about, and every page this board carries.
    showing: str
    pages: list[str]
    cols: int
    rows: int
    cells_total: float
    cells_used: float
    cells_free: float
    # How many widgets are taking up room, which is not how many exist: a widget
    # inside a folded group is on the board's books and not on its surface.
    item_count: int
    largest_free_rect: Placement | None
