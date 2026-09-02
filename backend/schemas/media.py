"""The media widget: a queue of things to play, and what the browser says it did.

Its own module rather than another block in ``schemas.payloads`` for the reason
``colour.py`` and ``icon.py`` are: a widget with a queue, a transport and a
report is several models, and the payload file is already at the house limit.
Everything here is re-exported from ``schemas.payloads`` and ``schemas.board``,
so nothing outside has to know it moved.

A track is either a file on this machine or a video on YouTube. A local track is
named by a path and served by the widget's id and the track's place in the
queue: a filesystem path never appears in a URL, the same rule the image and
video widgets have always followed. A YouTube track is named by its video id and
played by YouTube's own player, so nothing about it is served from here.
"""

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, get_args
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

# What the browser will actually play. Anything else is refused when the queue is
# built, because a queue that silently drops a file leaves the caller believing
# it queued nineteen tracks when it queued eighteen.
AUDIO_SUFFIXES = frozenset({".mp3", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav"})
VIDEO_SUFFIXES = frozenset({".mp4", ".m4v", ".webm", ".mkv", ".mov", ".ogv"})

# Audio and video are what a local file turns out to be; ``youtube`` is the
# third because where a track comes from decides how it is played, and this is
# the one field that already travels with every track.
TrackKind = Literal["audio", "video", "youtube"]

# Every host a YouTube link arrives on. The short one is what the Share button
# gives, and the music and mobile ones are what a phone pastes.
YOUTUBE_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
)

# A video id is eleven characters of URL-safe base64 and has been for the life
# of the site. Nothing else matches it: an absolute path has slashes in it and a
# filename has a dot, and neither is in this alphabet.
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

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


def youtube_id(source: str) -> str | None:
    """The video id inside whatever a person pasted, or ``None`` when it is not YouTube.

    A watch URL from the address bar, a ``youtu.be`` link from the Share button
    and a bare id from ``yt-dlp`` all come out as the same eleven characters,
    because all three are what somebody actually has to hand.

    A link that is plainly YouTube and yet carries no id raises instead of
    falling through to being treated as a filename, which would come back as
    "not an audio or video file" — a true sentence about the wrong problem.
    """
    text = source.strip()
    if _VIDEO_ID.match(text):
        return text
    # A pasted link often has no scheme on it. Prefixing the authority marker
    # makes ``youtube.com/watch?v=…`` parse as a host rather than as a path.
    parsed = urlparse(text if "//" in text else f"//{text}", scheme="https")
    if (parsed.hostname or "").lower() not in YOUTUBE_HOSTS:
        return None
    # The watch URL carries the id in a query; every other shape — the short
    # link, a Short, an embed, a stream — carries it as the last path segment.
    found = parse_qs(parsed.query).get("v", [parsed.path.rsplit("/", 1)[-1]])[0]
    if not _VIDEO_ID.match(found):
        raise ValueError(f"{source!r} is a YouTube link with no video id in it")
    return found


class MediaTrack(BaseModel):
    """One entry in the queue: a file on this machine, or a video on YouTube.

    Exactly one of ``path`` and ``youtube`` is set, and which one it is decides
    how the widget plays it. Everything else about a track — its place in the
    queue, its title, the transport that drives it — is the same either way,
    which is why this is one model and not two widgets.

    ``kind`` and ``title`` are filled in from whichever was given when nobody
    says otherwise, so a caller that has nineteen filenames and no metadata still
    gets a queue that reads properly on the TV. Both can be overridden: a
    filename is a guess at a title, not the title.
    """

    model_config = ConfigDict(extra="forbid")

    path: str | None = None
    # A YouTube video id. Accepts any shape of link on the way in and keeps only
    # the id, so what is stored is the one thing every caller agrees on.
    youtube: str | None = None
    title: str | None = None
    kind: TrackKind | None = None

    @model_validator(mode="after")
    def _fill_in(self) -> "MediaTrack":
        """Derive what the source already says, and refuse what cannot be played."""
        if (self.path is None) == (self.youtube is None):
            raise ValueError("a track is either a path or a youtube video, and not both")
        if self.youtube is not None:
            found = youtube_id(self.youtube)
            if found is None:
                raise ValueError(f"{self.youtube!r} is not a YouTube video id or link")
            self.youtube = found
            self.kind = "youtube"
            # The id is a poor thing to read across a room, but it is the only
            # name a link carries. The page replaces it with the real title once
            # YouTube's player hands one over.
            self.title = self.title or found
            return self
        if self.kind is None or self.kind == "youtube":
            kind = kind_of(self.path)
            if kind is None:
                raise ValueError(f"{self.path!r} is not an audio or video file this board can play")
            self.kind = kind
        if self.title is None:
            self.title = Path(self.path).stem
        return self


class MediaPayload(BaseModel):
    """A queue of files and YouTube videos, and where in it the widget is.

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
