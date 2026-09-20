"""The board the rig measures, and the numbers that keep arriving on it.

A fixture rather than the television's own `state/board.hud`, for two reasons.
It has to exist in a fresh clone — a rig that only runs on one machine cannot
compare anything to a number taken on another. And it has to hold still: the
real board gains and loses widgets as the house is used, so a figure taken from
it in March and one taken in September are two different boards, which is the
failure this whole directory exists to prevent.

So this is a deliberately fixed board: one widget of every chart kind, plus two
blocks of words for the extrusion to have scaffolding to carry. Charts, because
charts turned out to be the entire cost of the board (#133) — everything else
measured at about a twentieth of a core together.

`--board <path>` overrides it, and pointing that at `state/board.hud` is how you
ask "what does *my* board cost" rather than "what does a change cost". The
second question is the one that compares across time.
"""

from __future__ import annotations

import random
from typing import Any

# Every number the feed invents comes from here, so two runs of the rig see the
# same sequence. A sweep interleaves arms against each other and a difference
# has to come from the code, not from one arm having been handed livelier data.
SEED = 20260919

# What the agent actually does: a collector writes its panel every three
# seconds. Recharts animates for 300 ms after each write (`SWEEP_MS`), so the
# cadence and the sweep together set the duty cycle, and the duty cycle is what
# #133 turned out to be about. Measuring at any other cadence measures a board
# nobody runs.
CADENCE_S = 3.0

HISTORY = 24


def _item(
    ident: str, key: str, payload: dict[str, Any], box: tuple[float, float, float, float]
) -> dict[str, Any]:
    x, y, w, h = box
    return {
        "id": ident,
        "key": key,
        "description": None,
        "color": "#ffffffa6",
        "border": None,
        "scale": None,
        "flat": False,
        "payload": payload,
        "playback": None,
        "page": "main",
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "parent_id": None,
        "created_at": "2026-09-19T00:00:00Z",
    }


def _chart(
    chart: str, data: list[dict[str, Any]], x_key: str, series: list[str], **rest: Any
) -> dict[str, Any]:
    return {
        "kind": "chart",
        "chart": chart,
        "data": data,
        "x_key": x_key,
        "series": series,
        "title": rest.get("title"),
        "icon": rest.get("icon"),
        "max": rest.get("max"),
        "unit": None,
        "axes": rest.get("axes", "both"),
        "unfilled": rest.get("unfilled"),
        "colors": rest.get("colors", ["#ffffffa6"]),
        "thresholds": rest.get("thresholds", []),
    }


class Board:
    """The fixture board, and the next reading for every panel on it.

    Holds its own random source so a run is reproducible, and holds the history
    windows so a line chart slides rather than being redrawn from nothing.
    """

    def __init__(self, cores: int = 8) -> None:
        self._rng = random.Random(SEED)
        self._cores = cores
        self._history: dict[str, list[dict[str, Any]]] = {
            "net": [{"t": str(i), "in": 40.0, "out": 12.0} for i in range(HISTORY)],
            "load": [{"t": str(i), "load": 3.0} for i in range(HISTORY)],
        }
        self._tick = 0

    def items(self) -> list[dict[str, Any]]:
        """Every widget, with whatever reading it is showing now."""
        return [
            _item("radar0000cpu", "cpu", self._cpu(), (0, 0, 6, 6)),
            _item("radial000mem", "mem", self._gauge("RAM", 56.6), (6, 0, 5, 5)),
            _item("radial000gpu", "gpu", self._gauge("GPU", 78.0), (11, 0, 5, 5)),
            _item("bar00000disk", "disk", self._disk(), (16, 0, 8, 6)),
            _item("line00000net", "net", self._line(), (0, 6, 10, 6)),
            _item("area0000load", "load", self._area(), (10, 6, 10, 6)),
            _item("pie00000mem2", "split", self._pie(), (20, 6, 8, 6)),
            _item("note00000one", "note", {"kind": "note", "text": "the rig"}, (0, 12, 8, 3)),
            _item(
                "text00000two",
                "text",
                {"kind": "text", "text": "what the board costs", "size": "lg"},
                (8, 12, 8, 3),
            ),
        ]

    def panels(self) -> list[dict[str, Any]]:
        """The widgets a reading lands on — every chart, and nothing else.

        The words do not change between readings on the real board either: a
        collector writes a number, and a caption stays where it was put.
        """
        return [i for i in self.items() if i["payload"]["kind"] == "chart"]

    def advance(self) -> None:
        """Take the next reading. Jitter, not noise: the numbers stay plausible."""
        self._tick += 1
        for window in self._history.values():
            window.pop(0)
            last = window[-1]
            nxt: dict[str, Any] = {"t": str(self._tick + HISTORY)}
            for series, value in last.items():
                if series == "t":
                    continue
                nxt[series] = round(
                    max(0.0, min(100.0, float(value) + self._rng.uniform(-6, 6))), 1
                )
            window.append(nxt)

    def _jitter(self, mid: float, spread: float) -> float:
        return round(max(0.0, min(100.0, mid + self._rng.uniform(-spread, spread))), 1)

    def _cpu(self) -> dict[str, Any]:
        data = [{"core": str(c), "use": self._jitter(28, 12)} for c in range(self._cores)]
        return _chart("radar", data, "core", ["use"], icon="cpu", max=100.0)

    def _gauge(self, title: str, mid: float) -> dict[str, Any]:
        data = [{"label": "", "use": self._jitter(mid, 8)}]
        return _chart(
            "radial",
            data,
            "label",
            ["use"],
            title=title,
            max=100.0,
            unfilled="#ffffff80",
            thresholds=[{"at": 77.0, "color": "#ff2b1c"}],
        )

    def _disk(self) -> dict[str, Any]:
        names = ("root", "home", "data", "snap")
        data = [{"mount": n, "used": self._jitter(50, 25)} for n in names]
        return _chart("bar", data, "mount", ["used"], title="disk", max=100.0)

    def _line(self) -> dict[str, Any]:
        return _chart("line", list(self._history["net"]), "t", ["in", "out"], title="net", axes="y")

    def _area(self) -> dict[str, Any]:
        return _chart("area", list(self._history["load"]), "t", ["load"], title="load", axes="y")

    def _pie(self) -> dict[str, Any]:
        data = [{"what": w, "share": self._jitter(25, 10)} for w in ("app", "cache", "free")]
        return _chart("pie", data, "what", ["share"], title="memory")
