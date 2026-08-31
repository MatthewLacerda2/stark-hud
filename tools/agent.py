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

Row = dict[str, Any]


# ------------------------------------------------------------------- board
class Board:
    """The HTTP side.

    Panels are addressed by the name they were given, so this holds no state at
    all. It used to keep a file mapping names to item ids; when that file went
    missing the panels it had made were unclaimable, every write collided with
    them, and the board silently froze on its last values.
    """

    def __init__(self, api: str) -> None:
        self.api = api

    def call(self, method: str, path: str, body: dict | None = None) -> Any:
        """One request. Returns None on failure, having said why."""
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self.api}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:200]
            print(f"  ! {method} {path}: {exc.code} {detail}", file=sys.stderr)
        except OSError as exc:
            print(f"  ! {method} {path}: {exc}", file=sys.stderr)
        return None

    def write(self, key: str, payload: dict, place: dict) -> None:
        """Create or update the panel called ``key``.

        ``place`` only takes effect the first time; the board ignores it after,
        so a panel someone dragged stays dragged.
        """
        self.call("PUT", f"/board/items/by-key/{key}", {"payload": payload, **place})


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
        # No source of data: the panel is whatever the config says it is. Used
        # for a widget that is fed some other way — the inbox gets its contents
        # over the socket, it just needs to exist and stay put.
        return []

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
        wants strings in `items`, a feed wants entries in `entries`, and
        anything else wants text. The source only has to print the content; the
        config already says what it is.
        """
        panel = dict(self.spec["panel"])
        kind = panel.get("kind", "note")

        if isinstance(produced, str):
            panel["items" if kind == "list" else "text"] = (
                produced.splitlines() if kind == "list" else produced
            )
            return panel

        rows = produced if isinstance(produced, list) else [produced]
        if not rows and "command" not in self.spec and "url" not in self.spec:
            return panel  # a static widget: nothing to fold in
        if kind == "list":
            panel["items"] = [str(row) for row in rows]
            return panel
        if kind == "feed":
            # Rows are already whole entries; a feed is replaced, never appended
            # to, so history would only fight whoever polled it.
            panel["entries"] = rows
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
        board.write(source.name, source.payload(produced), source.spec.get("place", {}))


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
