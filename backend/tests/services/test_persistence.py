"""The board has to come back after a restart, widgets and notifications alike."""

from pathlib import Path

from repositories import board, notifications, store
from schemas.board import NotePayload
from schemas.notifications import NotificationCreate
from services import persistence


def _point_at(tmp_path: Path, monkeypatch) -> Path:
    target = tmp_path / "board.hud"
    monkeypatch.setattr(store, "path", lambda: target)
    return target


def test_round_trip_keeps_items_and_notifications(tmp_path, monkeypatch):
    target = _point_at(tmp_path, monkeypatch)
    item = board.add(NotePayload(text="hello"), 0, 0, 4, 2, None, False, key="greeting")
    notifications.add(NotificationCreate(title="done", source="test"))

    assert persistence.save()
    assert target.exists()

    board.clear()
    notifications.clear()
    persistence.restore()

    restored = board.list_items()
    assert [i.id for i in restored] == [item.id]
    assert restored[0].key == "greeting"
    assert [n.title for n in notifications.list_all()] == ["done"]


def test_unreadable_file_is_moved_aside_not_obeyed(tmp_path, monkeypatch):
    target = _point_at(tmp_path, monkeypatch)
    target.write_text("this is not a board", encoding="utf-8")

    persistence.restore()

    assert board.list_items() == []
    assert target.with_suffix(".hud.bad").exists()
    assert not target.exists()


def test_a_board_we_cannot_read_is_left_where_it_is(tmp_path, monkeypatch):
    """A permission error says nothing about the contents. Do not quarantine it."""
    target = _point_at(tmp_path, monkeypatch)
    target.write_text("{}", encoding="utf-8")

    def refuse(*_args, **_kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_text", refuse)
    persistence.restore()

    assert target.exists()
    assert not target.with_suffix(".hud.bad").exists()


def test_a_mutation_marks_the_board_dirty(tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch)
    persistence.save()
    assert not store.dirty()

    board.add(NotePayload(text="anything"), 0, 0, 2, 2, None, False)
    assert store.dirty()
