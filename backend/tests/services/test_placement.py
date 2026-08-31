"""Grid placement: first-fit search, bounds, and occupancy reporting."""

from datetime import UTC, datetime

import pytest

from schemas.board import ChartPayload, ItemRead, NotePayload, Placement
from services.placement import BoardFullError, default_size, find_slot

COLS, ROWS = 12, 8


def _item(x: int, y: int, w: int, h: int, item_id: str = "i") -> ItemRead:
    """Build a placed item for occupancy maths."""
    return ItemRead(
        id=item_id,
        payload=NotePayload(text="x"),
        x=x,
        y=y,
        w=w,
        h=h,
        parent_id=None,
        pinned=False,
        created_at=datetime.now(UTC),
    )


def test_default_size_follows_the_kind() -> None:
    """A video gets more room than a note, because it needs it."""
    assert default_size(NotePayload(text="x")) == (3, 2)
    assert default_size(ChartPayload(chart="bar", data=[], x_key="k", series=["a"])) == (4, 3)


def test_find_slot_scans_top_left_first() -> None:
    """The first free slot is chosen, so the board fills predictably."""
    assert find_slot([], 3, 2, COLS, ROWS) == Placement(x=0, y=0, w=3, h=2)
    taken = [_item(0, 0, 3, 2)]
    assert find_slot(taken, 3, 2, COLS, ROWS) == Placement(x=3, y=0, w=3, h=2)


def test_find_slot_raises_when_nothing_fits() -> None:
    """A full board raises rather than overlapping or shrinking."""
    full = [_item(0, 0, COLS, ROWS)]
    with pytest.raises(BoardFullError) as excinfo:
        find_slot(full, 1, 1, COLS, ROWS)
    assert excinfo.value.cells_free == 0
