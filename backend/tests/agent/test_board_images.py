"""Hanging a picture: where it goes, what shape it is padded to, and its id.

What the pictures are of left this repository with the watcher that makes them
(they are one instance's project, and `state/` holds those now). How a picture
gets onto a board did not: it is the board's kit, it is the part with the two
bugs worth remembering — a cropped plot, and a widget that shows its first
picture for ever — and so it is the part still tested here.
"""

import pathlib

import pytest
from agent import Board
from board_images import Picture, hang_all, take_down

FIRST = {"x": 19.0, "y": 4.0, "w": 13.0, "h": 7.0}


class _Wall(Board):
    """A board holding these widgets, remembering what it was asked to do."""

    def __init__(self, up: list[dict]):
        super().__init__("http://nowhere")
        self.up = up
        self.calls: list[tuple[str, str]] = []
        self.posted: dict[str, dict] = {}

    def call(self, method: str, path: str, body: dict | None = None):
        self.calls.append((method, path))
        if method == "POST" and body:
            self.posted[body["key"]] = body
        return self.up if method == "GET" else None


@pytest.fixture
def padded(monkeypatch) -> dict[str, float]:
    """What each picture was padded to, instead of running Pillow."""
    shapes: dict[str, float] = {}

    def letterbox(python, source, target, aspect):
        shapes[target.stem] = aspect
        return True

    monkeypatch.setattr("board_images.letterbox", letterbox)
    return shapes


def _picture(tmp_path: pathlib.Path, key: str = "curve") -> Picture:
    image = tmp_path / f"{key}.png"
    image.write_bytes(b"png")
    return Picture(key=key, image=image, alt=key, description="a note", first=FIRST)


def test_a_picture_goes_where_it_was_first_put(tmp_path, padded):
    board = _Wall([])

    hang_all(board, [_picture(tmp_path)], tmp_path / "cache", pathlib.Path("python"))

    assert {k: board.posted["curve"][k] for k in FIRST} == FIRST
    assert padded["curve"] == pytest.approx(13.0 / 7.0)


def test_a_picture_somebody_dragged_stays_dragged_and_is_padded_to_that_shape(tmp_path, padded):
    """Padding it to its first shape would letterbox it against the wrong edges."""
    moved = {"id": "old", "key": "curve", "x": 0.0, "y": 0.0, "w": 10.0, "h": 5.0}
    board = _Wall([moved])

    hang_all(board, [_picture(tmp_path)], tmp_path / "cache", pathlib.Path("python"))

    assert {k: board.posted["curve"][k] for k in ("x", "y", "w", "h")} == {
        "x": 0.0,
        "y": 0.0,
        "w": 10.0,
        "h": 5.0,
    }
    assert padded["curve"] == pytest.approx(2.0)


def test_a_picture_is_re_hung_under_a_new_id_rather_than_rewritten(tmp_path, padded):
    """The board serves an image at /media/<id>, so a browser has no reason to
    fetch it again while the id is the same: one URL would freeze on picture one."""
    board = _Wall([{"id": "old", "key": "curve", "x": 0.0, "y": 0.0, "w": 10.0, "h": 5.0}])

    hang_all(board, [_picture(tmp_path)], tmp_path / "cache", pathlib.Path("python"))

    assert ("DELETE", "/board/items/old") in board.calls
    assert ("POST", "/board/items") in board.calls


def test_a_picture_that_was_not_drawn_leaves_the_last_one_up(tmp_path, padded):
    """A plotter that skipped a sheet should not take the old sheet down."""
    board = _Wall([])
    missing = Picture("gone", tmp_path / "nothing.png", "gone", "", FIRST)

    hang_all(board, [missing], tmp_path / "cache", pathlib.Path("python"))

    assert board.posted == {}
    assert not [call for call in board.calls if call[0] == "DELETE"]


def test_taking_a_widget_down_is_only_a_delete_of_what_is_there():
    board = _Wall([{"id": "retired", "key": "old_sheet"}])

    take_down(board, ["old_sheet", "never_hung"])

    assert [call for call in board.calls if call[0] == "DELETE"] == [
        ("DELETE", "/board/items/retired")
    ]
