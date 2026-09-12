"""Root test fixtures.

There is no database. The board is a module-level dict, so the only shared state
between tests is the board itself — cleared before and after each test so order
never matters.

Persistence is switched off here before anything imports the settings: a test
run should never touch, or be steered by, the board that is on the TV.
"""

import os

os.environ.setdefault("STATE_FILE", "")

import pytest

from repositories import board, notifications
from services import origin


@pytest.fixture(autouse=True)
def clean_board() -> None:
    """Empty the board around every test.

    The origin window is emptied with it: it counts what has gone out in the
    last couple of seconds, and a test that creates six widgets would otherwise
    decide how many the next test is allowed to announce.
    """
    origin.burst.clear()
    board.clear()
    board.set_background(None)
    board.set_ink(None)
    notifications.clear()
    yield
    board.clear()
    board.set_background(None)
    board.set_ink(None)
    notifications.clear()
