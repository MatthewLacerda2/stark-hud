"""Groups: the trade of room that folding makes, and what it refuses.

A group is a handful of widgets on one page that fold away together. What
matters is that folding is a trade — the widgets come off the board and the
group takes their place — and that either half of it can be refused rather than
shoved through. Holding more than one screenful is a page's job, and lives in
``test_pages.py``.
"""

import pytest

from repositories import board as repo
from schemas.board import GroupPayload, ItemCreate, ItemUpdate, NotePayload
from services import board as service
from services import groups, pages
from services.groups import NestedGroupError, NoRoomError


async def _note(x: float, y: float, w: float = 4, h: float = 3):
    """A note somewhere in particular."""
    return await service.create(ItemCreate(payload=NotePayload(text="x"), x=x, y=y, w=w, h=h))


async def _group(*items):
    """A group holding these widgets."""
    group = await service.create(ItemCreate(payload=GroupPayload()))
    await groups.gather(group, list(items))
    return repo.get(group.id)


async def test_an_open_group_takes_up_no_room():
    """Grouping moves nothing: the widgets are where they always were."""
    note = await _note(0, 0)
    group = await _group(note)

    assert group.payload.state == "open"
    assert [i.id for i in groups.on_board(repo.list_items())] == [note.id]
    assert service.status().item_count == 1


async def test_folding_frees_the_room_its_widgets_were_using():
    """The whole point: five widgets become one, and the board has space again."""
    held = [await _note(0, 0), await _note(4, 0), await _note(8, 0)]
    group = await groups.fold(await _group(*held))

    on_board = groups.on_board(repo.list_items())
    assert [i.id for i in on_board] == [group.id]
    assert service.status().cells_used == group.w * group.h


async def test_a_folded_group_draws_where_its_widgets_were():
    """A fold you have to go and look for is not a fold."""
    await _note(0, 0)  # somebody else, so the corner is not simply free
    group = await groups.fold(await _group(await _note(10, 4), await _note(16, 8)))

    assert (group.x, group.y) == (10, 4)


async def test_unfolding_puts_everything_back_where_it_was():
    """Folding is not a move: the widgets return to their own coordinates."""
    note = await _note(10, 4)
    group = await groups.fold(await _group(note))
    await groups.unfold(repo.get(group.id))

    back = repo.get(note.id)
    assert (back.x, back.y) == (10, 4)
    assert [i.id for i in groups.on_board(repo.list_items())] == [note.id]


async def test_unfolding_is_refused_when_the_room_was_taken():
    """Nothing is shoved aside, and the refusal names what is in the way."""
    near, far = await _note(0, 0), await _note(20, 10)
    group = await groups.fold(await _group(near, far))
    squatter = await _note(20, 10)

    with pytest.raises(NoRoomError) as excinfo:
        await groups.unfold(repo.get(group.id))
    assert far.id in str(excinfo.value)
    assert squatter.id in str(excinfo.value)


async def test_a_group_does_not_hold_a_group():
    """Nesting stops at one level, because a tree is hard to hold in your head."""
    inner = await _group(await _note(0, 0))
    outer = await service.create(ItemCreate(payload=GroupPayload()))

    with pytest.raises(NestedGroupError):
        await groups.gather(outer, [inner])


async def test_a_folded_widget_is_placed_but_not_checked():
    """Its coordinates are a note of where it comes back to, tested on the unfold."""
    near, far = await _note(0, 0), await _note(20, 10)
    group = await groups.fold(await _group(near, far))
    loose = await _note(10, 4)

    # Nothing refuses this: the folded widget is not on the board to collide.
    moved = await service.update(repo.get(far.id), ItemUpdate(x=loose.x, y=loose.y))
    assert (moved.x, moved.y) == (10, 4)

    # The bill arrives on the way back out, which is where it belongs.
    with pytest.raises(NoRoomError):
        await groups.unfold(repo.get(group.id))


async def test_removing_a_group_gives_its_widgets_back():
    """Losing a container never silently takes its contents with it."""
    note = await _note(10, 4)
    group = await groups.fold(await _group(note))
    await service.remove(repo.get(group.id))

    assert repo.get(group.id) is None
    assert repo.get(note.id).parent_id is None
    assert [i.id for i in groups.on_board(repo.list_items())] == [note.id]


async def test_a_group_is_folded_against_its_own_page():
    """The only board a fold can disturb is the one its widgets are on."""
    group = await groups.fold(await _group(await _note(0, 0, 32, 18)))
    await pages.send([repo.get(group.id)], "planning")
    await _note(0, 0, 32, 18)  # the whole of the default page, where the group was

    # The fold comes back on the page it went to, which has nothing else on it.
    await groups.unfold(repo.get(group.id))
    assert [i.page for i in groups.on_board(pages.on(repo.list_items(), "planning"))] == [
        "planning"
    ]


async def test_joining_a_group_brings_a_widget_onto_its_page():
    """A group and its widgets are one thing on one board."""
    group = await service.create(ItemCreate(payload=GroupPayload()))
    await pages.show("planning")
    elsewhere = await _note(0, 0)

    await groups.gather(repo.get(group.id), [elsewhere])

    assert repo.get(elsewhere.id).page == "main"


async def test_a_widget_is_not_grouped_onto_a_page_with_no_room_for_it():
    """It really does move, so it is checked like anything else that moves."""
    group = await service.create(ItemCreate(payload=GroupPayload()))
    await _note(0, 0, 8, 6)
    await pages.show("planning")
    elsewhere = await _note(0, 0, 8, 6)

    with pytest.raises(NoRoomError):
        await groups.gather(repo.get(group.id), [elsewhere])
    assert repo.get(elsewhere.id).page == "planning"


async def test_the_refusal_names_every_blocker_and_how_far_in_it_is():
    """A quarter of a column is a nudge; half a widget is a conversation.

    Both are "no" to ``illegal``, which names the first pair it finds and stops.
    A caller deciding between moving something and going back to the user needs
    all of them, and the size of each.
    """
    held = [await _note(0, 0), await _note(8, 0), await _note(16, 0)]
    group = await groups.fold(await _group(*held))
    sliver = await _note(11.75, 0, 4, 3)  # a quarter of a column into the second
    squarely = await _note(16, 0, 4, 3)  # the whole of the third

    with pytest.raises(NoRoomError) as excinfo:
        await groups.unfold(repo.get(group.id))

    said = str(excinfo.value)
    assert "2 widgets are in the room" in said
    assert f"{sliver.id} is 0.25x3 into" in said
    assert f"{squarely.id} is 4x3 into" in said


async def test_the_refusal_hands_back_the_blockers_as_well_as_the_sentence():
    """Every caller here is blind, so a refusal that can be read as data is."""
    note = await _note(20, 10)
    # The group also holds the corner, so it folds there rather than over the
    # room this test is about.
    group = await groups.fold(await _group(await _note(0, 0), note))
    squatter = await _note(20, 10)

    with pytest.raises(NoRoomError) as excinfo:
        await groups.unfold(repo.get(group.id))

    assert excinfo.value.extra() == {
        "group": group.id,
        "blockers": [{"id": squatter.id, "over": note.id, "overlap": [4.0, 3.0]}],
    }


async def test_the_room_a_fold_is_holding_is_measured_on_its_own_page():
    """A page is a whole board, so a widget on another one is not in the way."""
    note = await _note(20, 10)
    group = await groups.fold(await _group(await _note(0, 0), note))
    await pages.show("planning")
    await _note(20, 10)  # the same corner of a different board

    await groups.unfold(repo.get(group.id))

    assert repo.get(group.id).payload.state == "open"
    assert note.id in {i.id for i in groups.on_board(pages.on(repo.list_items(), "main"))}


async def test_somebody_standing_in_the_room_is_named_before_the_unfold():
    """The whole point: told while you are still holding the thing in the way."""
    note = await _note(20, 10)
    group = await groups.fold(await _group(await _note(0, 0), note))
    squatter = await _note(20, 10)

    crowding = groups.blocked(repo.get(group.id), repo.list_items())
    assert [(a.id, b.id) for a, b, _dx, _dy in crowding] == [(note.id, squatter.id)]
    # And nothing refused it. The room is free while the group is folded, which
    # is what folding is for.
    assert repo.get(squatter.id) is not None
