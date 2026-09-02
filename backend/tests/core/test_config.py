"""Settings: grid bounds, CORS parsing, and the voice's own numbers."""

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


def test_the_board_reads_a_shade_slower_than_the_vendor_would() -> None:
    """The one voice setting that is not ElevenLabs': at 1.0 it is fast for a room."""
    assert Settings().ELEVENLABS_SPEED == 0.95


@pytest.mark.parametrize(
    "field, value",
    [
        ("ELEVENLABS_SPEED", 1.5),
        ("ELEVENLABS_STABILITY", 2.0),
        ("ELEVENLABS_SIMILARITY_BOOST", -0.1),
        ("ELEVENLABS_STYLE", 1.1),
    ],
)
def test_a_voice_setting_out_of_range_stops_the_backend_and_names_itself(
    field: str, value: float
) -> None:
    """Caught at startup, not as a 422 the moment somebody wanted to hear something."""
    with pytest.raises(ValidationError, match=field):
        Settings(**{field: value})
