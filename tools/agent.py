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

    def announce(self, entry: dict) -> None:
        """Put one line in the board's inbox.

        A different verb from `write` because it is a different thing. A panel is
        replaced and holds one current value; a notification is an event, and the
        board keeps every one it is given until it ages out.
        """
        self.call("POST", "/notifications", entry)

    def write(self, key: str, payload: dict, place: dict) -> None:
        """Create or update the panel called ``key``.

        ``place`` only takes effect the first time; the board ignores it after,
        so a panel someone dragged stays dragged.
        """
        self.call("PUT", f"/board/items/by-key/{key}", {"payload": payload, **place})


# ------------------------------------------------------------------ reading
#
# Split in two on purpose. `fetch` is where the machine is touched — a
# subprocess, a socket — and can only really be exercised by having the machine
# there. `interpret` is where the answer is shaped, takes a string and returns a
# value, and is the half that has actually had the bugs in it.
def fetch(source: dict) -> str | None:
    """Run a source and return what it printed, or None if it failed.

    A command prints on stdout, a URL answers with a body. A source declaring
    neither has nothing to run: the panel is whatever the config says it is,
    which is how a widget fed some other way — the inbox, over the socket —
    gets to exist and stay put.
    """
    if "command" in source:
        # {collectors} so the config does not have to know where it was checked
        # out to, and can be run from any working directory.
        command = source["command"].format(collectors=Path(__file__).parent / "collectors")
        try:
            return subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=source.get("timeout", 20),
                check=True,
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"  ! {source['name']}: {exc}", file=sys.stderr)
            return None
    if "url" in source:
        try:
            with urllib.request.urlopen(source["url"], timeout=10) as response:
                return response.read().decode()
        except (urllib.error.HTTPError, OSError) as exc:
            print(f"  ! {source['name']}: {exc}", file=sys.stderr)
            return None
    return ""


def interpret(out: str, json_path: str = "", name: str = "") -> list[Row] | str | None:
    """What a source printed, as a value: rows, or the text of a note.

    Anything that will not parse as JSON is text, deliberately. A collector that
    prints a sentence is a note that says the sentence, which is more useful on
    a television than a panel that went blank.
    """
    try:
        value = json.loads(out)
    except ValueError:
        return out.strip()  # not JSON: treat it as the text of a note

    for key in filter(None, json_path.split(".")):
        if not isinstance(value, dict) or key not in value:
            print(f"  ! {name}: no {json_path!r} in the response", file=sys.stderr)
            return None
        value = value[key]
    return value


def read_source(source: dict) -> list[Row] | str | None:
    """Run a source and shape what it produced, or None if either half failed."""
    out = fetch(source)
    if out is None:
        return None
    if not source.get("command") and not source.get("url"):
        return []
    return interpret(out, source.get("json_path", ""), source["name"])


# ------------------------------------------------------------------ running
def _mark(row: Row) -> str:
    """What makes this announcement the same announcement as last time."""
    return str(row.get("key") or row.get("title", ""))


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
        # `notifications = true` sends what this source prints to the inbox
        # instead of into a panel. There is no `panel` on such a source: the rows
        # are the notifications, already shaped.
        self.announces = bool(spec.get("notifications", False))
        # What was true last time this ran. Not what has ever been said: a
        # condition that clears and comes back is news again, and remembering it
        # forever would silence the second time a disk filled up.
        self.said: set[str] = set()

    def news(self, rows: list[Row]) -> list[Row]:
        """The rows that were not already true last time, ready to post.

        Identity is `key` where there is one, because a title carries the number
        and the number moves: "3 packages" and "4 packages" are one piece of news
        told twice, and an inbox that repeats itself is one nobody reads.

        `key` is dropped on the way out. It is this agent's bookkeeping and the
        board has never heard of it — the notification model forbids fields it
        does not know, so leaving it on would turn every announcement into a 422.
        """
        fresh = [row for row in rows if _mark(row) not in self.said]
        self.said = {_mark(row) for row in rows}
        return [{k: v for k, v in row.items() if k != "key"} for row in fresh]

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
        if source.announces:
            for entry in source.news(produced if isinstance(produced, list) else []):
                board.announce(entry)
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
