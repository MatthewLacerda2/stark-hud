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

    # Served openly on the LAN by design: no auth, any device on the wifi may
    # read and write the board.
    HOST: str = "0.0.0.0"  # noqa: S104
    PORT: int = 8000

    CORS_ORIGINS: str = "*"

    # Where the board is kept between runs. Empty means keep nothing, which is
    # what the tests want. The extension is ours; the contents are plain JSON,
    # so the file can be edited, copied, or swapped for another board.
    STATE_FILE: str = "state/board.hud"

    # How long the board may be ahead of the file on disk. Every change is
    # written whole, so this is a batching window, not a risk window: a power
    # cut loses at most this many seconds of the screen.
    STATE_FLUSH_SECONDS: float = 5.0

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse the comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance."""
    return Settings()
