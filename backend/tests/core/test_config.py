"""Settings: grid bounds and CORS parsing."""

import pytest
from pydantic import ValidationError

from core.config import Settings


def test_grid_defaults_are_16_by_9_doubled() -> None:
    """32x18 keeps cells square on a 1080p panel."""
    settings = Settings()
    assert (settings.GRID_COLS, settings.GRID_ROWS) == (32, 18)
    assert settings.GRID_COLS / settings.GRID_ROWS == 16 / 9


def test_a_zero_width_grid_is_refused() -> None:
    """A grid with no columns would accept items it can never show."""
    with pytest.raises(ValidationError):
        Settings(GRID_COLS=0)


def test_cors_origins_are_split_and_stripped() -> None:
    """The comma-separated env var becomes a clean list."""
    settings = Settings(CORS_ORIGINS="http://a ,  http://b ,")
    assert settings.cors_origins_list == ["http://a", "http://b"]
