"""A batch, judged by the arrangement it produces rather than step by step.

The case this exists for is the swap: two widgets of the same size trade
places, which is an overlap at every moment in between and a perfectly legal
board at the end. On a full board there is nowhere to park one of them, so one
call at a time the swap is not slow — it is impossible.
"""

import pytest

from repositories import board as repo
from schemas.board import Change, GroupPayload, ItemCreate, NotePayload
from services import arrange, groups
from services import board as service
from services.arrange import RepeatedTargetError, UnknownTargetError
from services.placement import NoRoomError

COLS, ROWS = 32, 18


def _note(x: float, y: float, w: float = 16, h: float = 9, key: str | None = None):
    """A note somewhere in particular."""
    return service.create(ItemCreate(payload=NotePayload(text="x"), x=x, y=y, w=w, h=h, key=key))


def _fill():
    """Four notes that widget the whole board, so nothing can be parked."""
    return [_note(x, y) for y in (0, 9) for x in (0, 16)]


def test_two_widgets_swap_on_a_board_with_nowhere_to_park():
    """The whole point: no intermediate state exists, and none is needed."""
    a, b, *_ = _fill()

    arrange.rearrange(
        [
            Change(target=a.id, x=b.x, y=b.y),
            Change(target=b.id, x=a.x, y=a.y),
        ]
    )

    assert (repo.get(a.id).x, repo.get(a.id).y) == (16, 0)
    assert (repo.get(b.id).x, repo.get(b.id).y) == (0, 0)


def test_a_rejected_batch_changes_nothing():
    """A half-rearranged board on a television nobody is standing at is worse."""
    a, b, *_ = _fill()

    with pytest.raises(NoRoomError):
        arrange.rearrange([Change(target=a.id, x=b.x, y=b.y)])

    assert (repo.get(a.id).x, repo.get(a.id).y) == (0, 0)


def test_a_refusal_names_both_widgets_and_where():
    """The caller cannot see the board, so "no" on its own is useless to it."""
    a, b, *_ = _fill()

    with pytest.raises(NoRoomError) as excinfo:
        arrange.rearrange([Change(target=a.id, x=b.x, y=b.y)])

    assert a.id in str(excinfo.value)
    assert b.id in str(excinfo.value)
    assert "same place" in str(excinfo.value)


def test_a_widget_may_be_named_by_its_key():
    """A key is what a session actually remembers, and it names one widget."""
    panel = _note(0, 0, key="cpu")

    arrange.rearrange([Change(target="cpu", x=16, y=9)])

    assert (repo.get(panel.id).x, repo.get(panel.id).y) == (16, 9)


def test_moving_and_resizing_are_one_entry():
    """An entry is where a widget ends up, not a verb applied to it."""
    note = _note(0, 0)

    arrange.rearrange([Change(target=note.id, x=4, y=2, w=8, h=4, opacity=0.5)])

    after = repo.get(note.id)
    assert (after.x, after.y, after.w, after.h, after.opacity) == (4, 2, 8, 4, 0.5)


def test_a_removal_makes_room_for_the_move_in_the_same_batch():
    """Removal and arrival are one thought when the end state is what is judged."""
    a, b, *_ = _fill()

    arrange.rearrange([Change(target=b.id, remove=True), Change(target=a.id, x=b.x, y=b.y)])

    assert repo.get(b.id) is None
    assert (repo.get(a.id).x, repo.get(a.id).y) == (16, 0)


def test_a_missing_target_stops_the_whole_batch():
    """Three of four moved is not what anybody asked for."""
    a, *_ = _fill()

    with pytest.raises(UnknownTargetError):
        arrange.rearrange([Change(target=a.id, x=0, y=9), Change(target="nope", x=0)])

    assert (repo.get(a.id).x, repo.get(a.id).y) == (0, 0)


def test_naming_one_widget_twice_is_refused():
    """Two entries are two answers to where it ends up; say it once."""
    a, *_ = _fill()

    with pytest.raises(RepeatedTargetError):
        arrange.rearrange([Change(target=a.id, x=0), Change(target=a.id, y=9)])


def test_removing_a_folded_group_is_judged_with_its_widgets_back_on_the_board():
    """Losing a container never silently takes its contents with it."""
    near, far = _note(0, 0, 4, 3), _note(20, 10, 4, 3)
    group = service.create(ItemCreate(payload=GroupPayload()))
    groups.gather(group, [near, far])
    folded = groups.fold(repo.get(group.id))
    _note(20, 10, 4, 3)  # somebody took the room while it was folded

    with pytest.raises(NoRoomError):
        arrange.rearrange([Change(target=folded.id, remove=True)])

    assert repo.get(folded.id) is not None
