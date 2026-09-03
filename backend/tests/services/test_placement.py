"""Placement: first-fit search over edges, bounds, and occupancy reporting."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schemas.board import MIN_SIZE, ChartPayload, ItemRead, NotePayload, Placement
from services.placement import BoardFullError, default_size, find_slot

COLS, ROWS = 12, 8


def _item(x: float, y: float, w: float, h: float, item_id: str = "i") -> ItemRead:
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
    assert default_size(NotePayload(text="x")) == (8, 4)
    assert default_size(ChartPayload(chart="bar", data=[], x_key="k", series=["a"])) == (10, 7)


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


def test_find_slot_places_between_two_widgets() -> None:
    """The only fit is the hole between them, and edges are how it is found."""
    walls = [_item(0, 0, 4, ROWS, "left"), _item(7, 0, COLS - 7, ROWS, "right")]
    assert find_slot(walls, 3, 2, COLS, ROWS) == Placement(x=4, y=0, w=3, h=2)
    with pytest.raises(BoardFullError):
        find_slot(walls, 4, 2, COLS, ROWS)


def test_a_decimal_widget_leaves_a_decimal_edge() -> None:
    """Fractions are ordinary: the next item lands flush against 3.5, not 4."""
    taken = [_item(0, 0, 3.5, 2)]
    assert find_slot(taken, 2, 2, COLS, ROWS) == Placement(x=3.5, y=0, w=2, h=2)


def test_the_smallest_widget_is_a_quarter_cell() -> None:
    """Below the floor a widget is not small, it is invisible and still in the way."""
    assert Placement(x=0, y=0, w=MIN_SIZE, h=MIN_SIZE).w == MIN_SIZE
    with pytest.raises(ValidationError):
        Placement(x=0, y=0, w=MIN_SIZE / 2, h=1)
