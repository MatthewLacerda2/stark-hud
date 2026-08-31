#!/usr/bin/env python3
"""Keep the board fed from whatever this machine can see.

The board never fetches — it draws what it is given — so something has to push,
and this is it. Sources are declared in a TOML file, each saying three things:
where the data comes from, how often, and which panel it lands in.

    python tools/agent.py                    # run forever
    python tools/agent.py --once             # one pass, for testing
    python tools/agent.py --config other.toml

Sources live in a file on this machine, deliberately, and never on the board.
The board is open to anyone on the LAN; if it carried commands, anyone on the
wifi could run code here. A display should not be a remote shell.

Standard library only, so cron or a systemd unit can run it with no virtualenv.
"""

import argparse
import json
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path(__file__).parent / "sources.toml"
DEFAULT_API = "http://127.0.0.1:8000/api/v1"
STATE = Path.home() / ".local/state/stark-hud-panels.json"

Row = dict[str, Any]


# ------------------------------------------------------------------- board
class Board:
    """The HTTP side: upsert a named panel, remembering what it became."""

    def __init__(self, api: str) -> None:
        self.api = api
        self.ids: dict[str, str] = self._load()

    @staticmethod
    def _load() -> dict[str, str]:
        try:
            return json.loads(STATE.read_text())
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(self.ids, indent=2))

    def call(self, method: str, path: str, body: dict | None = None) -> Any:
        """One request. Returns None for anything that is not a 2xx."""
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self.api}{path}", data=data, method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except (urllib.error.HTTPError, OSError):
            return None

    def upsert(self, name: str, payload: dict, place: dict) -> None:
        """Update the panel if it is still there, otherwise create it.

        Updating in place is what lets somebody drag a tile and keep it: a
        refresh rewrites the contents and leaves x, y, w and h alone.
        """
        item_id = self.ids.get(name)
        if item_id and self.call("PATCH", f"/board/items/{item_id}", {"payload": payload}):
            return
        created = self.call("POST", "/board/items", {"payload": payload, **place})
        if created:
            self.ids[name] = created["id"]
            self._save()


# ------------------------------------------------------------------ reading
def read_source(source: dict) -> list[Row] | str | None:
    """Run a source and return what it produced, or None if it failed.

    A command prints JSON on stdout. A URL returns JSON. Either way the shape is
    the chart's rows, or a string for a note.
    """
    if "command" in source:
        # {collectors} so the config does not have to know where it was checked
        # out to, and can be run from any working directory.
        command = source["command"].format(collectors=Path(__file__).parent / "collectors")
        try:
            out = subprocess.run(
                command, shell=True, capture_output=True,
                text=True, timeout=source.get("timeout", 20), check=True,
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"  ! {source['name']}: {exc}", file=sys.stderr)
            return None
    elif "url" in source:
        try:
            with urllib.request.urlopen(source["url"], timeout=10) as response:
                out = response.read().decode()
        except (urllib.error.HTTPError, OSError) as exc:
            print(f"  ! {source['name']}: {exc}", file=sys.stderr)
            return None
    else:
        print(f"  ! {source['name']}: needs a command or a url", file=sys.stderr)
        return None

    try:
        value = json.loads(out)
    except ValueError:
        return out.strip()  # not JSON: treat it as the text of a note

    for key in filter(None, source.get("json_path", "").split(".")):
        if not isinstance(value, dict) or key not in value:
            print(f"  ! {source['name']}: no {source['json_path']!r} in the response",
                  file=sys.stderr)
            return None
        value = value[key]
    return value


# ------------------------------------------------------------------ running
class Source:
    """One declared source, and when it is next due."""

    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.name: str = spec["name"]
        self.every: float = float(spec.get("every", 30))
        self.due = 0.0
        # `history = N` turns a one-row source into a series: the agent keeps the
        # last N samples so a collector never has to remember anything.
        depth = int(spec.get("history", 0))
        self.history: deque[Row] | None = deque(maxlen=depth) if depth else None

    def payload(self, produced: list[Row] | str) -> dict:
        """Fold what the source produced into the declared panel.

        Where it lands depends on the kind: a chart wants rows in `data`, a list
        wants strings in `items`, and anything else wants text. The source only
        has to print the content; the config already says what it is.
        """
        panel = dict(self.spec["panel"])
        kind = panel.get("kind", "note")

        if isinstance(produced, str):
            panel["items" if kind == "list" else "text"] = (
                produced.splitlines() if kind == "list" else produced
            )
            return panel

        rows = produced if isinstance(produced, list) else [produced]
        if kind == "list":
            panel["items"] = [str(row) for row in rows]
            return panel

        if self.history is not None:
            self.history.extend(rows)
            rows = list(self.history)
        panel["data"] = rows
        return panel


def tick(board: Board, sources: list[Source], now: float) -> None:
    """Run every source that is due."""
    for source in sources:
        if now < source.due:
            continue
        source.due = now + source.every
        produced = read_source(source.spec)
        if produced is None:
            continue
        board.upsert(source.name, source.payload(produced), source.spec.get("place", {}))


def main() -> None:
    """Load the config and keep it running."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--once", action="store_true", help="one pass, then exit")
    args = parser.parse_args()

    config = tomllib.loads(args.config.read_text())
    sources = [Source(s) for s in config.get("source", [])]
    if not sources:
        sys.exit(f"no sources declared in {args.config}")

    board = Board(args.api)
    print(f"{len(sources)} sources from {args.config}")
    while True:
        tick(board, sources, time.monotonic())
        if args.once:
            return
        time.sleep(1)


if __name__ == "__main__":
    main()
