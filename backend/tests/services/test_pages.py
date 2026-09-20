"""Pages: a whole board each, one of them showing, and the turn between them.

What matters is that turning the page changes nothing but which page is showing
— no widget moves, none is rebuilt, and none stops taking writes — and that
every judgement the board makes about room is made against one page.
"""

import pytest

from repositories import board as repo
from schemas.board import DEFAULT_PAGE, GroupPayload, ItemCreate, ItemUpdate, NotePayload
from services import board as service
from services import groups, pages
from services.pages import GroupSplitError, NoRoomError


async def _note(x: float, y: float, w: float = 4, h: float = 3, text: str = "x"):
    """A note somewhere in particular, on whatever page is showing."""
    return await service.create(ItemCreate(payload=NotePayload(text=text), x=x, y=y, w=w, h=h))


async def test_a_new_widget_lands_on_the_page_that_is_showing():
    """The bag a widget goes in is the page somebody is looking at."""
    await pages.show("planning")
    note = await _note(0, 0)

    assert note.page == "planning"
    assert [i.id for i in pages.drawn(repo.list_items())] == [note.id]


async def test_turning_to_a_page_that_does_not_exist_shows_an_empty_board():
    """That is how a new page is started: there is nothing to create."""
    await _note(0, 0)
    await pages.show("planning")

    assert pages.showing() == "planning"
    assert pages.drawn(repo.list_items()) == []
    assert service.status().item_count == 0


async def test_each_page_has_the_whole_grid_to_itself():
    """Two boards' worth of layout, and neither has to make room for the other."""
    first = await _note(0, 0, 32, 18, "the ordinary board")
    await pages.show("planning")
    second = await _note(0, 0, 32, 18, "planning")

    assert [i.id for i in pages.drawn(repo.list_items())] == [second.id]
    await pages.show(DEFAULT_PAGE)
    assert [i.id for i in pages.drawn(repo.list_items())] == [first.id]


async def test_turning_the_page_moves_nothing():
    """A page keeps its own layout, so the one you left is the one you get back."""
    here = [await _note(0, 0), await _note(8, 4), await _note(20, 10)]
    before = [(i.id, i.x, i.y, i.w, i.h) for i in here]

    await pages.show("planning")
    await _note(0, 0, 32, 18)
    await pages.show(DEFAULT_PAGE)

    after = [(i.id, i.x, i.y, i.w, i.h) for i in pages.drawn(repo.list_items())]
    assert after == before


async def test_a_panel_on_a_page_that_is_not_showing_still_takes_writes():
    """Not asleep, which is what makes turning back a cut and not a rebuild."""
    panel = await service.create(ItemCreate(payload=NotePayload(text="stale"), key="cpu", x=0, y=0))
    await pages.show("planning")
    await _note(0, 0, 32, 18)  # the whole of this page, where the panel still thinks it is

    written = await service.update(
        repo.get_by_key("cpu"), ItemUpdate(payload=NotePayload(text="now"))
    )

    assert written.payload.text == "now"
    assert written.page == DEFAULT_PAGE
    assert panel.id not in {i.id for i in pages.drawn(repo.list_items())}


async def test_a_page_comes_back_exactly_as_it_was_left():
    """The definition of done, end to end: build, turn away, turn back."""
    loose = await _note(0, 0)
    group = await service.create(ItemCreate(payload=GroupPayload()))
    await groups.gather(group, [await _note(8, 4), await _note(16, 4)])
    folded = await groups.fold(repo.get(group.id))

    await pages.show("planning")
    await _note(0, 0, 32, 18)
    board = await pages.show(DEFAULT_PAGE)

    drawn = pages.drawn(board)
    assert {i.id for i in drawn} == {loose.id, folded.id}
    assert [(i.x, i.y) for i in drawn if i.id == folded.id] == [(8, 4)]


async def test_a_group_travels_with_what_it_holds():
    """A group is on one page, so naming it sends its widgets too."""
    group = await service.create(ItemCreate(payload=GroupPayload()))
    inside = await groups.gather(group, [await _note(0, 0), await _note(8, 0)])

    await pages.send([repo.get(group.id)], "planning")

    assert {i.page for i in repo.list_items()} == {"planning"}
    assert [repo.get(i.id).page for i in inside] == ["planning", "planning"]


async def test_a_widget_is_not_sent_out_from_under_its_group():
    """Half a group on another page is a shelf on a board its widgets left."""
    group = await service.create(ItemCreate(payload=GroupPayload()))
    inside = await groups.gather(group, [await _note(0, 0)])

    with pytest.raises(GroupSplitError) as excinfo:
        await pages.send(inside, "planning")
    assert group.id in str(excinfo.value)


async def test_sending_is_refused_when_the_far_page_has_no_room():
    """Nothing is shoved aside there either, and half a screen arriving is worse."""
    await pages.show("planning")
    await _note(0, 0, 32, 18)
    await pages.show(DEFAULT_PAGE)
    going = await _note(0, 0)

    with pytest.raises(NoRoomError):
        await pages.send([going], "planning")
    assert repo.get(going.id).page == DEFAULT_PAGE


async def test_a_page_with_nothing_on_it_is_still_a_page_you_can_name():
    """The showing page and the one the board starts on are always listed."""
    await _note(0, 0)
    await pages.show("planning")

    assert pages.names(repo.list_items()) == [DEFAULT_PAGE, "planning"]
    assert service.status().pages == [DEFAULT_PAGE, "planning"]
    assert service.status().showing == "planning"


async def test_no_name_at_all_is_the_page_the_board_starts_on():
    """So a session that has turned the board can always get the ordinary one back."""
    await pages.show("planning")
    await pages.show("")

    assert pages.showing() == DEFAULT_PAGE
