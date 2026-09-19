#!/usr/bin/env python3
"""Hanging pictures on the board, and taking them down.

Anything that produces pictures rather than rows — a plotter's sheets, a
camera's stills — needs two things the board does not do for it, and they are
both here. Nothing in this file knows what the pictures are of: what they show
and when they are worth redrawing belongs to whatever watcher made them, which
for an instance's own project is a script in `state/`.

The HTTP is `agent.Board`, passed in. This file used to carry its own copy of
that client, with a different timeout and a different log line, which is how two
clients to one board came to disagree about what a failure looks like.
"""

from __future__ import annotations

import datetime
import pathlib
import subprocess
from typing import NamedTuple

from agent import Board


class Picture(NamedTuple):
    """One picture and the widget it goes into."""

    key: str
    image: pathlib.Path
    alt: str
    description: str
    first: dict  # x/y/w/h the first time it goes up, and only then


def log(message: str) -> None:
    """A line in the agent's log, stamped, since a watcher runs unattended."""
    print(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {message}", flush=True)


def letterbox(
    python: pathlib.Path, source: pathlib.Path, target: pathlib.Path, aspect: float
) -> bool:
    """Pad a picture to the widget's shape — see tools/letterbox.py for why.

    Run with whichever python has Pillow, because this machine's `python3` does
    not and everything under `tools/` is standard library only. A watcher that
    renders with a project's virtualenv already has one to hand.
    """
    done = subprocess.run(
        [
            str(python),
            str(pathlib.Path(__file__).parent / "letterbox.py"),
            str(source),
            str(target),
            str(aspect),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if done.returncode:
        log(f"letterbox failed: {done.stderr.strip()[-200:]}")
    return done.returncode == 0


def standing(board: Board) -> dict[str, dict]:
    """Every widget on the board that has a key, by that key."""
    items = board.call("GET", "/board/items") or []
    return {item["key"]: item for item in items if item.get("key")}


def take_down(board: Board, keys: list[str], up: dict[str, dict] | None = None) -> None:
    """Remove these widgets if they are there."""
    up = standing(board) if up is None else up
    for key in keys:
        if key in up:
            board.call("DELETE", f"/board/items/{up[key]['id']}")


def hang(board: Board, picture: Picture, image: pathlib.Path, where: dict) -> None:
    """Put one picture up at `where`.

    Removed and added rather than written in place: the board serves an image at
    /media/<item id>, so a browser has no reason to fetch it again while the id
    is the same, and a widget rewritten under one id would show its first
    picture for ever. A new id is a new URL. A mesh has `mesh.reloaded` for
    exactly this; an image has no equivalent.
    """
    take_down(board, [picture.key])
    board.call(
        "POST",
        "/board/items",
        {
            "key": picture.key,
            "payload": {"kind": "image", "path": str(image), "alt": picture.alt},
            "description": picture.description,
            **where,
        },
    )


def hang_all(
    board: Board, pictures: list[Picture], cache: pathlib.Path, python: pathlib.Path
) -> None:
    """Put up every picture that exists, each padded to its own widget's shape.

    Where a widget already is wins over where it was first put: somebody may
    have dragged it, and a picture padded to its old shape would be letterboxed
    against the wrong edges.
    """
    cache.mkdir(parents=True, exist_ok=True)
    up = standing(board)
    for picture in pictures:
        if not picture.image.exists():
            log(f"no {picture.image.name}")
            continue
        where = (
            {k: up[picture.key][k] for k in ("x", "y", "w", "h")}
            if picture.key in up
            else picture.first
        )
        padded = cache / f"{picture.key}.png"
        if letterbox(python, picture.image, padded, where["w"] / where["h"]):
            hang(board, picture, padded, where)
