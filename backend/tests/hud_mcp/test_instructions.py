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
        "kept on disk",  # why yesterday's board is still there
        "drag",  # why an item may have moved under it
        "dark",  # the widget convention
        "notify",  # how to announce finishing
        "written whole",  # why a list is the one thing you add to
        "set_description",  # the note on a widget that the TV never shows
<<<<<<< HEAD
        "wake_item",  # that a widget can be told work is coming
        "before you know the answer",  # and that it goes first, which is the only thing that matters
=======
        "free tier",  # what saying something out loud costs, and who pays
>>>>>>> origin/voice
    ):
        assert fact in instructions, f"instructions no longer mention {fact!r}"
