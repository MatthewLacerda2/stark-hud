"""Pages: a second screenful, and each one its own grid.

The board never scrolls, so a page is the only way to hold more than fits. What
matters is that pages do not see each other: the same slot must be free on one
and taken on another, or they are not really separate screens.
"""

import pytest

from repositories import board as repo
from schemas.board import ItemCreate, ItemUpdate, NotePayload
from services import board as service
from services.board import SlotTakenError

HERE = {"payload": NotePayload(text="x"), "x": 0, "y": 0, "w": 4, "h": 3}


def test_the_same_slot_is_free_on_another_page():
    service.create(ItemCreate(**HERE, page=0))
    second = service.create(ItemCreate(**HERE, page=1))

    assert (second.x, second.y, second.page) == (0, 0, 1)


def test_the_same_slot_is_still_taken_on_the_same_page():
    service.create(ItemCreate(**HERE, page=0))

    with pytest.raises(SlotTakenError):
        service.create(ItemCreate(**HERE, page=0))


def test_a_new_widget_lands_on_the_page_being_shown():
    repo.set_page(2)
    item = service.create(ItemCreate(payload=NotePayload(text="x")))

    assert item.page == 2


def test_moving_a_widget_to_another_page_frees_its_slot():
    first = service.create(ItemCreate(**HERE, page=0))
    service.update(first, ItemUpdate(page=1))

    landed = service.create(ItemCreate(**HERE, page=0))
    assert landed.page == 0
    assert repo.get(first.id).page == 1


def test_pages_are_counted_by_the_furthest_one_with_anything_on_it():
    assert service.page_count() == 1
    service.create(ItemCreate(payload=NotePayload(text="x"), page=3))
    assert service.page_count() == 4
