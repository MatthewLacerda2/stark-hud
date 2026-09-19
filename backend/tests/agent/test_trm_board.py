"""How far a training run is, read off the files it writes.

`trm_board.py` imports its sibling `board_images` by bare name, because it is
run as a script from `tools/`. So it is imported here with `tools/` on the path,
the way it finds itself when it runs.
"""

import importlib
import json
import pathlib
from types import ModuleType

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[3] / "tools"


@pytest.fixture
def trm_board(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The script, imported the way it imports itself."""
    monkeypatch.syspath_prepend(str(TOOLS))
    return importlib.import_module("trm_board")


def a_run(tmp_path: pathlib.Path, rows: list[str], **parameters: int) -> pathlib.Path:
    """A run directory holding these metrics rows and these recorded parameters."""
    (tmp_path / "metrics.csv").write_text("\n".join(["step,ce,wall_clock", *rows]) + "\n")
    (tmp_path / "run_metadata.json").write_text(json.dumps({"parameters": parameters}))
    return tmp_path


def test_progress_is_the_last_step_in_tokens_against_the_budget(
    trm_board: ModuleType, tmp_path: pathlib.Path
) -> None:
    """Tokens per step are multiplied out from the run's own record: 4 x 1 x 2 x 8."""
    run = a_run(
        tmp_path,
        ["1,5.0,2026-09-17T12:00:00Z", "10,4.0,2026-09-17T12:10:00Z", ""],
        TRAIN_TOKEN_BUDGET=6400,
        ACCUMULATION_STEPS=4,
        BATCH_SIZE=1,
        MAX_SEQ_LEN=8,
    )
    assert trm_board.progress(tmp_path, run) == (640, 6400)


def test_a_run_with_no_rows_yet_has_no_progress_to_draw(
    trm_board: ModuleType, tmp_path: pathlib.Path
) -> None:
    """A bar at zero would say the run has started when nothing says so yet."""
    run = a_run(tmp_path, [], TRAIN_TOKEN_BUDGET=6400)
    assert trm_board.progress(tmp_path, run) is None


def test_a_new_run_takes_the_retired_sheet_down_and_keeps_moved_ones_in_place(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, trm_board: ModuleType
) -> None:
    """The plotter's old combined sheet goes; a sheet someone moved stays where it
    was put and is padded to that widget's shape, not to its first place."""
    images = importlib.import_module("board_images")
    run = tmp_path / "run"
    run.mkdir()
    for _, filename, _, _ in images.SHEETS:
        (run / filename).write_bytes(b"png")
    standing = [
        {"id": "old", "key": "trm_health"},
        {"id": "curve", "key": "trm_curve", "x": 0.0, "y": 0.0, "w": 10.0, "h": 5.0},
    ]
    calls: list[tuple[str, str]] = []
    shapes: dict[str, float] = {}
    placed: dict[str, dict] = {}

    def board(method: str, path: str, body: dict | None = None) -> list | None:
        calls.append((method, path))
        if method == "POST" and body:
            placed[body["key"]] = {k: body[k] for k in ("x", "y", "w", "h")}
        return standing if method == "GET" else None

    def letterbox(source, target, aspect, repo) -> bool:
        shapes[target.stem] = aspect
        return True

    monkeypatch.setattr(images, "board", board)
    monkeypatch.setattr(images, "letterbox", letterbox)
    monkeypatch.setattr(images, "log", lambda _message: None)

    images.show(tmp_path, run, tmp_path / "cache")

    assert ("DELETE", "/board/items/old") in calls
    assert placed["trm_curve"] == {"x": 0.0, "y": 0.0, "w": 10.0, "h": 5.0}
    assert shapes["trm_curve"] == 2.0
    assert placed["trm_speed"] == {"x": 19.0, "y": 14.5, "w": 13.0, "h": 3.5}


def test_the_first_places_tile_without_touching() -> None:
    """Exact at five decimals and pairwise disjoint, so none is refused."""
    images = importlib.import_module("board_images")
    rects = [first for *_, first in images.SHEETS]
    for rect in rects:
        assert all(round(v, 5) == v for v in rect.values())
    for i, a in enumerate(rects):
        for b in rects[i + 1 :]:
            apart = (
                a["x"] + a["w"] <= b["x"]
                or b["x"] + b["w"] <= a["x"]
                or a["y"] + a["h"] <= b["y"]
                or b["y"] + b["h"] <= a["y"]
            )
            assert apart, (a, b)
