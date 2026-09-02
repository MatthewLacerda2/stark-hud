"""The media widget: a queue of local files, and what the browser says it did.

Its own module rather than another block in ``schemas.payloads`` for the reason
``colour.py`` and ``icon.py`` are: a widget with a queue, a transport and a
report is several models, and the payload file is already at the house limit.
Everything here is re-exported from ``schemas.payloads`` and ``schemas.board``,
so nothing outside has to know it moved.

A track is named by a path on this machine and served by the widget's id and the
track's place in the queue. A filesystem path never appears in a URL — the same
rule the image and video widgets have always followed.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

# What the browser will actually play. Anything else is refused when the queue is
# built, because a queue that silently drops a file leaves the caller believing
# it queued nineteen tracks when it queued eighteen.
AUDIO_SUFFIXES = frozenset({".mp3", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav"})
VIDEO_SUFFIXES = frozenset({".mp4", ".m4v", ".webm", ".mkv", ".mov", ".ogv"})

TrackKind = Literal["audio", "video"]

# States the widget can be in, in the browser's words. Four of them are events a
# media element fires; ``idle`` is the fifth because an empty queue is genuinely
# none of the others, and calling that "paused" would be a small lie the first
# person to read it would have to work out.
PlaybackState = Literal["idle", "playing", "paused", "ended", "failed"]

# What a session can ask the widget to do. Five verbs, each taking nothing but
# the widget itself — which is why they are one tool with an action rather than
# five tools that would each be a whole entry in every session's tool list.
MediaAction = Literal["play", "pause", "stop", "next", "back"]
MEDIA_ACTIONS: tuple[MediaAction, ...] = get_args(MediaAction)


def kind_of(path: str) -> TrackKind | None:
    """Whether a path is audio, video, or nothing this widget can play."""
    suffix = Path(path).suffix.lower()
    if suffix in AUDIO_SUFFIXES:
        return "audio"
    if suffix in VIDEO_SUFFIXES:
        return "video"
    return None


class MediaTrack(BaseModel):
    """One entry in the queue.

    ``kind`` and ``title`` are filled in from the path when nobody says
    otherwise, so a caller that has nineteen filenames and no metadata still gets
    a queue that reads properly on the TV. Both can be overridden: a filename is
    a guess at a title, not the title.
    """

    model_config = ConfigDict(extra="forbid")

    path: str
    title: str | None = None
    kind: TrackKind | None = None

    @model_validator(mode="after")
    def _fill_in(self) -> "MediaTrack":
        """Derive what the path already says, and refuse what cannot be played."""
        if self.kind is None:
            kind = kind_of(self.path)
            if kind is None:
                raise ValueError(f"{self.path!r} is not an audio or video file this board can play")
            self.kind = kind
        if self.title is None:
            self.title = Path(self.path).stem
        return self


class MediaPayload(BaseModel):
    """A queue of local files, and where in it the widget is.

    One kind for audio and video rather than two, because everything a queue
    needs — an order, a place in it, a transport, a loop — is the same either
    way, and the only difference is whether there is a picture to look at while
    it plays.

    The transport lives here, in the widget's own state, rather than in a stream
    of commands sent at the browser. The board is one direction — the server
    holds what is true and every client renders it — so a widget that could only
    be driven by a command nobody kept would forget what it was doing the moment
    the TV reloaded. What is here instead survives a reload, a restart, and a
    second browser looking at the same board.

    What the browser then *did* about it is not here: that is ``ItemRead.playback``,
    kept on the item, because a payload belongs to whoever writes the widget.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["media"] = "media"
    tracks: list[MediaTrack] = []
    # Where in the queue the widget is. Clamped rather than refused: a queue can
    # be replaced with a shorter one, and pointing past the end of it should cost
    # a track, not the widget.
    index: int = Field(default=0, ge=0)
    # Whether it should be playing. Not whether it *is* — that is the report.
    playing: bool = True
    # What happens when the queue runs out: start again from the top, or stop.
    loop: bool = False
    # Sound is on by default, unlike the video widget, which is muted because a
    # wall of widgets all making noise is unusable. This widget is the noise: a
    # muted album is not an album.
    muted: bool = False
    # Take the whole board and give it back. It is here rather than in a size
    # because the widget keeps its slot on the grid and returns to it.
    maximised: bool = False
    # Drawn above the queue when there is room — an album's name, usually, which
    # no filename carries.
    title: str | None = None

    @model_validator(mode="after")
    def _clamp(self) -> "MediaPayload":
        """Keep ``index`` pointing at a track, or at 0 when there are none."""
        if self.index >= len(self.tracks):
            self.index = 0
        return self

    @property
    def current(self) -> MediaTrack | None:
        """The track the widget is on, or ``None`` when the queue is empty."""
        return self.tracks[self.index] if self.tracks else None


class PlaybackReport(BaseModel):
    """What the browser says it is doing, on its way back to the server.

    This is the one flow on this board that runs browser to server. Everything
    else is written by whoever drives the board and rendered by the TV; only the
    TV knows whether a file actually decoded, so only the TV can say.
    """

    model_config = ConfigDict(extra="forbid")

    state: PlaybackState
    # Which track it is talking about. A report about a track the widget has
    # already moved past is stale and must not be allowed to move it again.
    track: int | None = Field(default=None, ge=0)
    # Why it failed, in the browser's words. Usually a missing file or a codec
    # nothing on this machine can decode.
    error: str | None = None


class Playback(BaseModel):
    """A report as it is kept on the item, with a name and a time added.

    The title is copied in so a session reading ``list_items`` learns what is
    playing without fetching the payload and counting to the index. The time is
    here so a report that stopped arriving is visibly old rather than quietly
    wrong.
    """

    model_config = ConfigDict(extra="forbid")

    state: PlaybackState
    track: int | None = None
    title: str | None = None
    error: str | None = None
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
