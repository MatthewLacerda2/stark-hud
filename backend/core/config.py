"""Application settings loaded from the environment and `.env`."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application configuration.

    Values come from environment variables first, then a local `.env` file.
    Unknown keys are ignored so the same `.env` can serve multiple services.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # The board is a fixed grid: the TV cannot scroll, so anything that does not
    # fit on screen would stay invisible forever. Items are placed in cells,
    # never in pixels; the browser derives cell size from the viewport.
    #
    # 32x18 is 16:9 doubled, so a cell is square on a 1080p panel and a half-cell
    # nudge is still a visible amount of screen.
    GRID_COLS: int = Field(default=32, ge=1, le=96)
    GRID_ROWS: int = Field(default=18, ge=1, le=54)

    CORS_ORIGINS: str = "*"

    # Where the board is kept between runs. Empty means keep nothing, which is
    # what the tests want. The extension is ours; the contents are plain JSON,
    # so the file can be edited, copied, or swapped for another board.
    STATE_FILE: str = "state/board.hud"

    # How long the board may be ahead of the file on disk. Every change is
    # written whole, so this is a batching window, not a risk window: a power
    # cut loses at most this many seconds of the screen.
    STATE_FLUSH_SECONDS: float = 5.0

    # Where a file handed over by a browser lands. Beside the board file, because
    # that is the one directory this backend owns and the one volume it can write
    # to. Relative here like `STATE_FILE`,
    # and absolute in the container for the same reason — see `docker-compose.yml`.
    #
    # It is also the only directory on this machine where the board deletes
    # anything it did not make itself.
    # A media queue mostly holds paths a session named — an album somewhere on a
    # disk full of them — and those are somebody's files. These are ours: they
    # arrived with no name on this machine and nothing but a widget refers to
    # them, so when no widget does, nothing does. See `services.uploads`.
    UPLOAD_DIR: str = "state/uploads"

    # How long an uploaded file nothing refers to is left alone before a sweep
    # may delete it.
    #
    # Receiving a file and playing it are two calls: the bytes land, and then
    # something puts the path into a queue. In between, the file is referenced by
    # nobody and is indistinguishable from one whose widget has just been taken
    # off the board. Without this window, removing any media widget in that gap
    # would delete a file that was a second away from being played. Five minutes
    # is far longer than the gap and far shorter than anybody notices the disk.
    UPLOAD_GRACE_SECONDS: float = Field(default=300.0, ge=0)

    # Where the board-ready copy of the background video is kept: smaller and
    # slower, made once from the original and played in its place. Beside the
    # others for the same reason they are here — the one directory this backend
    # owns. Only ever the copy: the original stays
    # wherever its owner keeps it. Empty makes no copies at all, which is what
    # the tests want and what a board with no ffmpeg gets anyway. See
    # `services.background`.
    BACKGROUND_DIR: str = "state/backgrounds"

    # How long a media widget that has finished playing stays on the board.
    #
    # A film that has played to its end holds a slot on a board that never
    # scrolls and refuses new widgets when it is full, and from the sofa nobody
    # takes it off. An hour is long enough that putting it back on is still the
    # same evening, and short enough that the board is clear by morning.
    #
    # Finished, not merely quiet: a paused film is somebody who means to come
    # back and never expires, and a looping queue never finishes at all.
    # `services.media_expiry` holds the rule and the list of states that mean it.
    MEDIA_EXPIRY_SECONDS: float = Field(default=3600.0, ge=0)

    # How often the board is looked over for one. This is the granularity of the
    # hour above rather than a second deadline: a widget goes between an hour and
    # an hour and a minute after it finished, which is not a difference anybody
    # in the room can see. The pass reads a list already in memory, so it is
    # cheap, not free.
    MEDIA_EXPIRY_CHECK_SECONDS: float = Field(default=60.0, gt=0)

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse the comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance."""
    return Settings()
