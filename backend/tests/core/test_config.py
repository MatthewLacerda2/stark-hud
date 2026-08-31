"""Settings: grid bounds and CORS parsing."""

import pytest
from pydantic import ValidationError

from core.config import Settings


def test_grid_defaults_suit_a_1080p_tv() -> None:
    """12x8 gives cells big enough to read from a sofa."""
    settings = Settings()
    assert (settings.GRID_COLS, settings.GRID_ROWS) == (12, 8)


def test_a_zero_width_grid_is_refused() -> None:
    """A grid with no columns would accept items it can never show."""
    with pytest.raises(ValidationError):
        Settings(GRID_COLS=0)


def test_cors_origins_are_split_and_stripped() -> None:
    """The comma-separated env var becomes a clean list."""
    settings = Settings(CORS_ORIGINS="http://a ,  http://b ,")
    assert settings.cors_origins_list == ["http://a", "http://b"]
