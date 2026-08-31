#!/usr/bin/env python3
"""Push what this machine knows about itself onto the board.

The board never fetches: it draws what it is given. So the machine pushes, and
this is the thing that does it. Standard library only, so it can be run from a
cron entry, a systemd timer, or a terminal, without a virtualenv.

Panels are remembered by name in a small state file, so a refresh PATCHes the
item that is already there instead of adding a second one. That is what keeps a
tile where somebody dragged it.

    python tools/push_stats.py            # once
    python tools/push_stats.py --loop 30  # every 30 seconds
"""

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8000/api/v1"
STATE = Path.home() / ".local/state/stark-hud-panels.json"
SAMPLE_SECONDS = 0.4


# --------------------------------------------------------------------- http
def call(method: str, path: str, body: dict | None = None) -> dict | None:
    """One HTTP call to the board. Returns None on any non-2xx."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{API}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError:
        return None
    except OSError:
        return None


def load_state() -> dict[str, str]:
    """Panel name -> item id, from the last run."""
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state: dict[str, str]) -> None:
    """Remember which item is which panel."""
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def upsert(state: dict[str, str], name: str, payload: dict, **place: int) -> None:
    """Update the panel if it still exists, otherwise create it."""
    item_id = state.get(name)
    if item_id and call("PATCH", f"/board/items/{item_id}", {"payload": payload}):
        return
    created = call("POST", "/board/items", {"payload": payload, **place})
    if created:
        state[name] = created["id"]


# ------------------------------------------------------------------ sensors
def cpu_per_core() -> list[dict[str, float | str]]:
    """Busy percentage per core, sampled over a short window (what htop shows)."""

    def snapshot() -> dict[str, tuple[int, int]]:
        out: dict[str, tuple[int, int]] = {}
        for line in Path("/proc/stat").read_text().splitlines():
            if not line.startswith("cpu") or line.startswith("cpu "):
                continue
            parts = line.split()
            values = [int(v) for v in parts[1:]]
            idle = values[3] + values[4]
            out[parts[0]] = (sum(values), idle)
        return out

    first = snapshot()
    time.sleep(SAMPLE_SECONDS)
    second = snapshot()

    rows: list[dict[str, float | str]] = []
    for core, (total2, idle2) in second.items():
        total1, idle1 = first[core]
        d_total, d_idle = total2 - total1, idle2 - idle1
        busy = 0.0 if d_total <= 0 else round((1 - d_idle / d_total) * 100, 1)
        rows.append({"core": core.removeprefix("cpu"), "use": busy})
    return rows


def memory_percent() -> float:
    """Used memory as a percentage."""
    fields = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, rest = line.partition(":")
        fields[key] = int(rest.split()[0])
    total = fields["MemTotal"]
    available = fields.get("MemAvailable", fields["MemFree"])
    return round((total - available) / total * 100, 1)


def gpu() -> dict[str, float] | None:
    """Utilisation, memory and temperature, the way nvtop reads them."""
    query = "utilization.gpu,memory.used,memory.total,temperature.gpu"
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return None
    used, total = float(out.split(",")[1]), float(out.split(",")[2])
    return {
        "util": float(out.split(",")[0]),
        "vram": round(used / total * 100, 1),
        "temp": float(out.split(",")[3]),
    }


def tmux_sessions() -> list[str]:
    """Names of the open tmux sessions."""
    try:
        out = subprocess.run(
            ["tmux", "ls", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line for line in out.splitlines() if line]


def notifications() -> list[str]:
    """Notification items currently on the board, newest last."""
    items = call("GET", "/board/items") or []
    return [
        f"{i['payload'].get('source') or '—'}: {i['payload']['message']}"
        for i in items
        if i["payload"]["kind"] == "notification"
    ]


# -------------------------------------------------------------------- panels
def refresh() -> None:
    """Push every panel once."""
    state = load_state()

    upsert(state, "cpu", {
        "kind": "chart", "chart": "bar", "title": "CPU por núcleo",
        "x_key": "core", "series": ["use"], "max": 100, "data": cpu_per_core(),
    }, x=0, y=0, w=12, h=7)

    upsert(state, "ram", {
        "kind": "chart", "chart": "radial", "title": "Memória",
        "x_key": "label", "series": ["use"], "unit": "%", "max": 100,
        "data": [{"label": "RAM", "use": memory_percent()}],
    }, x=12, y=0, w=6, h=7)

    stats = gpu()
    if stats:
        upsert(state, "gpu", {
            "kind": "chart", "chart": "bar", "title": "GPU",
            "x_key": "metric", "series": ["pct"], "max": 100, "data": [
                {"metric": "uso", "pct": stats["util"]},
                {"metric": "vram", "pct": stats["vram"]},
            ],
        }, x=18, y=0, w=8, h=7)
        upsert(state, "gputemp", {
            "kind": "chart", "chart": "radial", "title": "GPU",
            "x_key": "label", "series": ["temp"], "unit": "°C", "max": 90,
            "data": [{"label": "temperatura", "temp": stats["temp"]}],
        }, x=26, y=0, w=6, h=7)

    sessions = tmux_sessions()
    upsert(state, "tmux", {
        "kind": "note",
        "text": "tmux\n\n" + ("\n".join(sessions) if sessions else "(nenhuma sessão)"),
    }, x=0, y=7, w=8, h=8)

    notices = notifications()
    upsert(state, "notifs", {
        "kind": "note",
        "text": "notificações\n\n" + ("\n".join(notices) if notices else "(nenhuma)"),
    }, x=8, y=7, w=10, h=8)

    save_state(state)


def main() -> None:
    """Run once, or on a loop."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", type=float, metavar="SECONDS",
                        help="keep refreshing every SECONDS")
    args = parser.parse_args()

    while True:
        refresh()
        if not args.loop:
            return
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
