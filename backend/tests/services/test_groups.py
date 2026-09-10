"""Groups: the trade of room that folding makes, and what it refuses.

A group is the answer to holding more than one subject, and the thing pages
never managed. What matters is that folding is a trade — the widgets come off
the board and the group takes their place — and that either half of it can be
refused rather than shoved through.
"""

import pytest

from repositories import board as repo
from schemas.board import GroupPayload, ItemCreate, ItemUpdate, NotePayload
from services import board as service
from services import groups
from services.groups import NestedGroupError, NoRoomError


def _note(x: float, y: float, w: float = 4, h: float = 3):
    """A note somewhere in particular."""
    return service.create(ItemCreate(payload=NotePayload(text="x"), x=x, y=y, w=w, h=h))


def _group(*items):
    """A group holding these widgets."""
    group = service.create(ItemCreate(payload=GroupPayload()))
    groups.gather(group, list(items))
    return repo.get(group.id)


def test_an_open_group_takes_up_no_room():
    """Grouping moves nothing: the widgets are where they always were."""
    note = _note(0, 0)
    group = _group(note)

    assert group.payload.state == "open"
    assert [i.id for i in groups.on_board(repo.list_items())] == [note.id]
    assert service.status().item_count == 1


def test_folding_frees_the_room_its_widgets_were_using():
    """The whole point: five widgets become one, and the board has space again."""
    held = [_note(0, 0), _note(4, 0), _note(8, 0)]
    group = groups.fold(_group(*held))

    on_board = groups.on_board(repo.list_items())
    assert [i.id for i in on_board] == [group.id]
    assert service.status().cells_used == group.w * group.h


def test_a_folded_group_draws_where_its_widgets_were():
    """A fold you have to go and look for is not a fold."""
    _note(0, 0)  # somebody else, so the corner is not simply free
    group = groups.fold(_group(_note(10, 4), _note(16, 8)))

    assert (group.x, group.y) == (10, 4)


def test_unfolding_puts_everything_back_where_it_was():
    """Folding is not a move: the widgets return to their own coordinates."""
    note = _note(10, 4)
    group = groups.fold(_group(note))
    groups.unfold(repo.get(group.id))

    back = repo.get(note.id)
    assert (back.x, back.y) == (10, 4)
    assert [i.id for i in groups.on_board(repo.list_items())] == [note.id]


def test_unfolding_is_refused_when_the_room_was_taken():
    """Nothing is shoved aside, and the refusal names what is in the way."""
    near, far = _note(0, 0), _note(20, 10)
    group = groups.fold(_group(near, far))
    squatter = _note(20, 10)

    with pytest.raises(NoRoomError) as excinfo:
        groups.unfold(repo.get(group.id))
    assert far.id in str(excinfo.value)
    assert squatter.id in str(excinfo.value)


def test_a_group_does_not_hold_a_group():
    """Nesting stops at one level, because a tree is hard to hold in your head."""
    inner = _group(_note(0, 0))
    outer = service.create(ItemCreate(payload=GroupPayload()))

    with pytest.raises(NestedGroupError):
        groups.gather(outer, [inner])


def test_a_folded_widget_is_placed_but_not_checked():
    """Its coordinates are a note of where it comes back to, tested on the unfold."""
    near, far = _note(0, 0), _note(20, 10)
    group = groups.fold(_group(near, far))
    loose = _note(10, 4)

    # Nothing refuses this: the folded widget is not on the board to collide.
    moved = service.update(repo.get(far.id), ItemUpdate(x=loose.x, y=loose.y))
    assert (moved.x, moved.y) == (10, 4)

    # The bill arrives on the way back out, which is where it belongs.
    with pytest.raises(NoRoomError):
        groups.unfold(repo.get(group.id))


def test_removing_a_group_gives_its_widgets_back():
    """Losing a container never silently takes its contents with it."""
    note = _note(10, 4)
    group = groups.fold(_group(note))
    service.remove(repo.get(group.id))

    assert repo.get(group.id) is None
    assert repo.get(note.id).parent_id is None
    assert [i.id for i in groups.on_board(repo.list_items())] == [note.id]


def test_a_group_that_is_away_occupies_nothing():
    """A screen that is not showing: no widgets, no shelf, no room taken."""
    note = _note(0, 0, 8, 6)
    group = _group(note)
    groups.show(None)

    assert repo.get(group.id).payload.state == "away"
    assert groups.on_board(repo.list_items()) == []
    assert service.status().item_count == 0
    assert service.status().cells_used == 0

    # And the room its widgets are holding is somebody else's now.
    squatter = _note(0, 0, 8, 6)
    assert [i.id for i in groups.on_board(repo.list_items())] == [squatter.id]


def test_showing_swaps_one_full_board_for_another():
    """The whole reason this is one call: each screen wants the room the other has."""
    first = _group(_note(0, 0, 32, 18))
    groups.show(None)
    second = _group(_note(0, 0, 32, 18))

    # One at a time is not slow, it is impossible: the room is still the other's.
    with pytest.raises(NoRoomError):
        groups.unfold(repo.get(first.id))

    groups.show(repo.get(first.id))
    assert [i.parent_id for i in groups.on_board(repo.list_items())] == [first.id]
    assert repo.get(second.id).payload.state == "away"


def test_showing_a_group_puts_a_folded_one_away_too():
    """One screen at a time, whatever the others were doing a moment ago."""
    shelf = groups.fold(_group(_note(0, 0)))
    other = _group(_note(10, 4))
    groups.show(repo.get(other.id))

    assert repo.get(shelf.id).payload.state == "away"
    assert [i.id for i in groups.away(repo.list_items())] == [shelf.id]


def test_a_widget_on_a_screen_that_is_not_showing_is_still_writable():
    """Away is weightless, not asleep — which is what makes a switch back a cut."""
    note = _note(0, 0)
    group = _group(note)
    groups.show(None)

    written = service.update(repo.get(note.id), ItemUpdate(payload=NotePayload(text="current")))

    assert written.payload.text == "current"
    assert groups.on_board(repo.list_items()) == []
    assert repo.get(group.id).payload.state == "away"


def test_a_group_that_is_away_will_not_take_a_widget():
    """Membership changes while a group is open, which is when the room can see it."""
    group = _group(_note(0, 0))
    groups.show(None)
    loose = _note(10, 4)

    with pytest.raises(NoRoomError) as excinfo:
        groups.gather(repo.get(group.id), [loose])
    assert "away" in str(excinfo.value)
