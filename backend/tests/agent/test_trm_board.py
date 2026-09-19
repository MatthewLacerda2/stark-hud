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


def test_the_end_of_a_run_lowers_the_bar_and_leaves_the_sheets(
    monkeypatch: pytest.MonkeyPatch, trm_board: ModuleType
) -> None:
    """The last run's curves stay on the wall; only the bar has nothing to say."""
    images = importlib.import_module("board_images")
    standing = [
        {"id": "curve", "key": "trm_curve"},
        {"id": "health", "key": "trm_health"},
        {"id": "bar", "key": "trm_progress"},
    ]
    deleted: list[str] = []

    def board(method: str, path: str, body: dict | None = None) -> list | None:
        if method == "DELETE":
            deleted.append(path.rsplit("/", 1)[-1])
        return standing if method == "GET" else None

    monkeypatch.setattr(images, "board", board)
    monkeypatch.setattr(images, "log", lambda _message: None)

    images.lower_bar()

    assert deleted == ["bar"]
