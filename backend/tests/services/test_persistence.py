"""The board has to come back after a restart, widgets and notifications alike."""

import json
from pathlib import Path

from repositories import board, notifications, store
from schemas.board import GroupPayload, Ink, NotePayload
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


def test_round_trip_keeps_the_ink(tmp_path, monkeypatch):
    """The ink is the board's, not a widget's, so it has to survive with it."""
    _point_at(tmp_path, monkeypatch)
    board.set_ink(Ink(color="#ffffffa6"))

    assert persistence.save()
    board.set_ink(None)
    persistence.restore()

    assert board.get_ink() == Ink(color="#ffffffa6")


def test_a_board_written_before_the_ink_existed_asks_for_the_default(tmp_path, monkeypatch):
    """No ink in the file is not a broken file: it is the default, spelled null."""
    target = _point_at(tmp_path, monkeypatch)
    target.write_text(json.dumps({"hud": 2, "items": []}), encoding="utf-8")

    persistence.restore()

    assert board.get_ink() is None


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


def test_a_widget_this_build_cannot_read_costs_only_that_widget(tmp_path, monkeypatch):
    """A schema change must not take the whole board with it.

    This is not hypothetical: removing one field from a feed entry emptied the
    board — background, clock and every notification — because the file was
    validated as one document.
    """
    target = _point_at(tmp_path, monkeypatch)
    board.add(NotePayload(text="keeps"), 0, 0, 4, 2, None, False, key="good")
    notifications.add(NotificationCreate(title="also keeps"))
    persistence.save()

    document = json.loads(target.read_text(encoding="utf-8"))
    document["items"].append(
        {
            "id": "stale0000000",
            "payload": {"kind": "note", "text": "from an older build", "gone": 1},
            "x": 8,
            "y": 0,
            "w": 4,
            "h": 2,
            "parent_id": None,
            "pinned": False,
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    target.write_text(json.dumps(document), encoding="utf-8")

    board.clear()
    notifications.clear()
    persistence.restore()

    assert [i.key for i in board.list_items()] == ["good"]
    assert [n.title for n in notifications.list_all()] == ["also keeps"]
    assert target.exists(), "a file we could partly read is not spoiled"


def test_a_mutation_marks_the_board_dirty(tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch)
    persistence.save()
    assert not store.dirty()

    board.add(NotePayload(text="anything"), 0, 0, 2, 2, None, False)
    assert store.dirty()


def test_a_file_with_two_widgets_holding_one_key_loads_with_one():
    """The rule is enforced on the way in, and a file predates it.

    A widget that cannot answer to its name is unreachable rather than wrong, so
    the later claimant keeps everything it shows and loses only the name.
    """
    board.add(NotePayload(text="a"), 0, 0, 4, 2, None, False, key="cpu")
    board.add(NotePayload(text="b"), 4, 0, 4, 2, None, False, key="cpu")

    # The rule this tests has no public door: restore() calls it on the way past,
    # and going through restore() would test the file reader instead.
    kept = persistence._named_once(board.list_items())  # noqa: SLF001

    assert [i.key for i in kept] == ["cpu", None]
    assert [i.payload.text for i in kept] == ["a", "b"]


def test_a_format_2_board_loses_its_groups_and_comes_up_anyway(tmp_path, monkeypatch):
    """An old file is degraded, never fatal.

    A group used to say ``open: true`` and now says ``state``, and a payload
    refuses keys it does not know — so every group in a format-2 file fails
    validation and is dropped, one warning each. That is the trade this build
    took: what is lost is the screens, which can be built again, and what is not
    lost is the board coming up at all. A widget whose group went with it is
    loose rather than gone, the same as when a group is removed.
    """
    target = _point_at(tmp_path, monkeypatch)
    group = board.add(GroupPayload(), 0, 0, 4, 3, None, False)
    board.add(NotePayload(text="hello"), 0, 0, 4, 2, group.id, False)
    assert persistence.save()

    old = json.loads(target.read_text(encoding="utf-8"))
    old["hud"] = 2
    for entry in old["items"]:
        if entry["payload"]["kind"] == "group":
            entry["payload"] = {"kind": "group", "open": True}
    target.write_text(json.dumps(old), encoding="utf-8")

    board.clear()
    persistence.restore()

    kept = board.list_items()
    assert [i.payload.kind for i in kept] == ["note"]
    assert kept[0].parent_id is None


def _before_the_fold(path: str) -> dict:
    """A widget as a board written before the video kind went holds it.

    The shape of a real item, with a `video` payload in it: one local file, and
    the three flags that are now `playing`, `loop` and `muted` on a player.
    """
    return {
        "id": "clip00000001",
        "key": "trailer",
        "payload": {"kind": "video", "path": path, "autoplay": False, "loop": True, "muted": True},
        "x": 4.5,
        "y": 2,
        "w": 16,
        "h": 9,
        "parent_id": None,
        "pinned": False,
        "created_at": "2026-01-01T00:00:00Z",
    }


def test_a_stored_video_comes_up_as_the_player_it_is_now(tmp_path, monkeypatch):
    """Nobody loses a widget to a version bump: same id, same place, same name."""
    target = _point_at(tmp_path, monkeypatch)
    entry = _before_the_fold("/mnt/d_drive/Video/clip.mkv")
    target.write_text(json.dumps({"hud": 3, "items": [entry]}), encoding="utf-8")

    persistence.restore()

    (widget,) = board.list_items()
    assert widget.id == entry["id"]
    assert widget.key == "trailer"
    assert (widget.x, widget.y, widget.w, widget.h) == (4.5, 2, 16, 9)
    player = widget.payload
    assert player.kind == "media"
    assert [(t.path, t.kind) for t in player.tracks] == [("/mnt/d_drive/Video/clip.mkv", "video")]
    # `autoplay` is `playing`, and the other two come across as they were: a clip
    # that was silent and looping is still silent and still looping.
    assert (player.playing, player.loop, player.muted) == (False, True, True)


def test_the_upgraded_board_is_what_goes_back_to_disk(tmp_path, monkeypatch):
    """Read is also written, so `video` leaves the file at the next flush.

    Marked changed on the way in rather than left for the next write to happen
    along: what is in memory really does differ from the file it came off, which
    is the whole of what dirty means — and it gives the upgrade an end date.
    """
    target = _point_at(tmp_path, monkeypatch)
    assert persistence.save()
    target.write_text(
        json.dumps({"hud": 3, "items": [_before_the_fold("/clip.mp4")]}), encoding="utf-8"
    )
    assert not store.dirty()

    persistence.restore()
    assert store.dirty(), "an upgraded board is not the board that is on disk"
    assert persistence.save()

    written = json.loads(target.read_text(encoding="utf-8"))
    assert [e["payload"]["kind"] for e in written["items"]] == ["media"]
