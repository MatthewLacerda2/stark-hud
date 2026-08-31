"""What a session is told when it connects.

These are the first thing a model reads, and it plans against them. A number
typed by hand here went stale once already — the grid changed and the
instructions kept advertising the old one.
"""

from core.config import get_settings
from hud_mcp.server import build_server


def test_instructions_state_the_configured_grid() -> None:
    """The advertised grid is the real one, whatever it is set to."""
    settings = get_settings()
    instructions = build_server().instructions or ""
    assert f"{settings.GRID_COLS} columns by {settings.GRID_ROWS} rows" in instructions


def test_instructions_cover_what_a_session_cannot_guess() -> None:
    """The facts that are not discoverable from the tool list alone."""
    instructions = (build_server().instructions or "").lower()
    for fact in (
        "never scrolls",  # why a full board refuses
        "nothing is saved",  # why yesterday's board is gone
        "drag",  # why an item may have moved under it
        "dark",  # the tile convention
        "notify",  # how to announce finishing
    ):
        assert fact in instructions, f"instructions no longer mention {fact!r}"
