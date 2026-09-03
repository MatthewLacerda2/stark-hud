"""Explicit placements: bounds, collisions, and free-space reporting."""

from datetime import UTC, datetime

from schemas.board import ItemRead, NotePayload, Placement
from services.placement import is_free, largest_free_rect

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


def test_placement_must_fit_inside_the_grid() -> None:
    """Hanging off an edge is refused even on an empty board."""
    assert is_free([], Placement(x=9, y=0, w=3, h=1), COLS, ROWS)
    assert not is_free([], Placement(x=10, y=0, w=3, h=1), COLS, ROWS)
    assert not is_free([], Placement(x=0, y=7, w=1, h=2), COLS, ROWS)


def test_an_item_does_not_collide_with_itself() -> None:
    """Resizing in place is allowed: the item being moved is ignored."""
    existing = [_item(0, 0, 3, 2, item_id="a")]
    assert not is_free(existing, Placement(x=0, y=0, w=3, h=2), COLS, ROWS)
    assert is_free(existing, Placement(x=0, y=0, w=3, h=2), COLS, ROWS, ignore_id="a")


def test_largest_free_rect_shrinks_as_the_board_fills() -> None:
    """The reported rectangle is exact, so a caller can trust it."""
    assert largest_free_rect([], COLS, ROWS) == Placement(x=0, y=0, w=12, h=8)
    half = [_item(0, 0, COLS, 4)]
    assert largest_free_rect(half, COLS, ROWS) == Placement(x=0, y=4, w=12, h=4)
    assert largest_free_rect([_item(0, 0, COLS, ROWS)], COLS, ROWS) is None


def test_touching_edges_do_not_count_as_overlapping() -> None:
    """Flush is the normal result of sliding something up against something else."""
    existing = [_item(0, 0, 3.5, 2, item_id="a")]
    assert is_free(existing, Placement(x=3.5, y=0, w=2, h=2), COLS, ROWS)
    assert not is_free(existing, Placement(x=3.4, y=0, w=2, h=2), COLS, ROWS)


def test_largest_free_rect_measures_decimals() -> None:
    """The reported rectangle is exact whether or not the edges are whole."""
    strip = [_item(0, 0, COLS, 4.5)]
    assert largest_free_rect(strip, COLS, ROWS) == Placement(x=0, y=4.5, w=12, h=3.5)


def test_largest_free_rect_finds_a_gap_between_two_widgets() -> None:
    """A maximal rectangle is bounded by edges, so a hole between two is found."""
    walls = [_item(0, 0, 4, ROWS, "left"), _item(7, 0, COLS - 7, ROWS, "right")]
    assert largest_free_rect(walls, COLS, ROWS) == Placement(x=4, y=0, w=3, h=ROWS)
