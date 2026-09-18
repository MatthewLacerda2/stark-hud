#!/usr/bin/env python3
"""Hanging pictures on the board, and taking them down — and the bar beside them.

Split from `trm_board.py` because it is the other half of the job: that one
works out which training run deserves the wall, this one is the board's HTTP
side and knows nothing about training.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import subprocess
import urllib.error
import urllib.request

BOARD = "http://127.0.0.1:8000/api/v1"

# The right-hand column, three tiles down it. Cells are square (32x18 on a 16:9
# screen), so w/h is the aspect each sheet is letterboxed to.
COLUMN_X, COLUMN_W = 23.0, 9.0
COLUMN_TOP, COLUMN_BOTTOM = 4.0, 18.0
TILE_H = (COLUMN_BOTTOM - COLUMN_TOP) / 3

SHEETS = (
    (
        "trm_curve",
        "training_curve.png",
        "Train and held-out cross-entropy against tokens, with the LR schedule "
        "under it. The held-out line is the only thing on this board that says how "
        "good the model is; the rest is the run's health.",
    ),
    (
        "trm_health",
        "optimization_health.png",
        "Gradient norm against the clip, VRAM against the arena ceiling, f16 "
        "zero-gradient fraction, logit health. Gates, meant to look boring, and "
        "interesting only when one of them stops being boring.",
    ),
    (
        "trm_speed",
        "throughput_progress.png",
        "Tokens per second end to end, and tokens against the run's budget. "
        "Catches a crawling run or a crash-relaunch; a flat line is the good case.",
    ),
)

# The progress bar, in the strip between the tasks list and the row of gauges
# under it. Only where it first appears: after that it stays wherever it is put.
PROGRESS_KEY = "trm_progress"
PROGRESS_AT = {"x": 16.0, "y": 14.375, "w": 7.0, "h": 1.26}
PROGRESS_NOTE = (
    "How far the training run on the card is through its token budget: tokens "
    "trained on (last step in metrics.csv times tokens per optimizer step) "
    "against TRAIN_TOKEN_BUDGET, which is the number at the right end. Written "
    "every minute by tools/trm_board.py and taken down with the sheets an hour "
    "after the card goes quiet."
)

NOTE = (
    "Hung here by tools/trm_board.py, which runs the TinyRefinementModel "
    "plotter and puts its sheets up. Not hand-maintained and not redrawn here: "
    "to change what a panel shows, change that repo's instruments/plots.py. If "
    "this picture is stale, that script is not running."
)


def log(message: str) -> None:
    print(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {message}", flush=True)


def letterbox(
    source: pathlib.Path, target: pathlib.Path, aspect: float, repo: pathlib.Path
) -> bool:
    """Pad a sheet to the widget's shape — see tools/letterbox.py for why.

    Pillow lives in the model's virtualenv rather than in this machine's
    python3, so that script is run the same way the plotter is.
    """
    done = subprocess.run(
        [
            str(repo / "venv/bin/python"),
            str(pathlib.Path(__file__).parent / "letterbox.py"),
            str(source),
            str(target),
            str(aspect),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if done.returncode:
        log(f"letterbox failed: {done.stderr.strip()[-200:]}")
    return done.returncode == 0


def board(method: str, path: str, body: dict | None = None) -> dict | list | None:
    request = urllib.request.Request(
        f"{BOARD}{path}",
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"} if body else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
        return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        log(f"{method} {path}: {exc.code} {exc.read().decode(errors='replace')[:160]}")
    except OSError as exc:
        log(f"{method} {path}: {exc}")
    return None


def by_key() -> dict[str, dict]:
    return {item["key"]: item for item in (board("GET", "/board/items") or []) if item.get("key")}


def hang(key: str, image: pathlib.Path, index: int, alt: str, note: str) -> None:
    """Put one sheet up, keeping wherever the widget currently sits.

    Removed and added rather than written in place: the board serves an image at
    /media/<item id>, so a browser has no reason to fetch it again while the id
    is the same, and a widget rewritten under one id would show its first
    picture for ever. A new id is a new URL. A mesh has `mesh.reloaded` for
    exactly this; an image has no equivalent.
    """
    standing = by_key().get(key)
    where = (
        {k: standing[k] for k in ("x", "y", "w", "h")}
        if standing
        else {"x": COLUMN_X, "y": COLUMN_TOP + index * TILE_H, "w": COLUMN_W, "h": TILE_H}
    )
    if standing:
        board("DELETE", f"/board/items/{standing['id']}")
    board(
        "POST",
        "/board/items",
        {
            "key": key,
            "payload": {"kind": "image", "path": str(image), "alt": alt},
            "description": f"{note}\n\n{NOTE}",
            **where,
        },
    )


def show(repo: pathlib.Path, run: pathlib.Path, cache: pathlib.Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    for index, (key, filename, note) in enumerate(SHEETS):
        sheet = run / filename
        if not sheet.exists():
            log(f"{run.name}: no {filename}")
            continue
        padded = cache / f"{key}.png"
        if letterbox(sheet, padded, COLUMN_W / TILE_H, repo):
            hang(key, padded, index, f"{run.name} — {filename[:-4]}", note)
    log(f"{run.name}: board updated")


def measure(done: int, budget: int) -> None:
    """Write the run's progress bar, putting it up the first time."""
    payload = {
        "kind": "progress",
        "value": done,
        "max": budget,
        "title": "TRM",
        # The gauges' own track, so the bar reads as one more of them.
        "unfilled": "#ffffff80",
    }
    board(
        "PUT",
        f"/board/items/by-key/{PROGRESS_KEY}",
        {"payload": payload, "description": PROGRESS_NOTE, **PROGRESS_AT},
    )


def clear() -> None:
    standing = by_key()
    for key in (*(sheet[0] for sheet in SHEETS), PROGRESS_KEY):
        if key in standing:
            board("DELETE", f"/board/items/{standing[key]['id']}")
    log("board cleared")
