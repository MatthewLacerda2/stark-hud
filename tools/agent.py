#!/usr/bin/env python3
"""Keep the board fed from whatever this machine can see.

The board never fetches — it draws what it is given — so something has to push,
and this is it. Sources are declared in a TOML file, each saying three things:
where the data comes from, how often, and which panel it lands in.

    python tools/agent.py                    # run forever
    python tools/agent.py --once             # one pass, for testing
    python tools/agent.py --config other.toml

That file is `state/sources.toml`, beside the board file and outside this
repository: which panels a board has is the instance's data, not the board's
code. A fresh clone has no `state/` and runs from `tools/sources.example.toml`
until somebody copies it across. Either way it is re-read whenever it changes on
disk, so pointing a panel somewhere else is an edit rather than a restart —
`sources.py` is that half, and this one is the loop and the board's client.

Sources live in a file on this machine, deliberately, and never on the board.
The board is open to anyone on the LAN; if it carried commands, anyone on the
wifi could run code here. A display should not be a remote shell.

Standard library only, so cron or a systemd unit can run it with no virtualenv.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from sources import ANNOUNCEMENTS, JOB, Declared, Source, read_source

TOOLS = Path(__file__).resolve().parent
DEFAULT_CONFIG = TOOLS.parent / "state" / "sources.toml"
EXAMPLE_CONFIG = TOOLS / "sources.example.toml"
DEFAULT_API = "http://127.0.0.1:8000/api/v1"


class Board:
    """The HTTP side, and the only one: a watcher in `state/` imports this too.

    Panels are addressed by the name they were given, so this holds no state at
    all. It used to keep a file mapping names to item ids; when that file went
    missing the panels it had made were unclaimable, every write collided with
    them, and the board silently froze on its last values.
    """

    def __init__(self, api: str = DEFAULT_API) -> None:
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

    def write(
        self, key: str, payload: dict, place: dict, description: str = "", page: str = ""
    ) -> None:
        """Create or update the panel called ``key``.

        ``place`` and ``page`` only take effect the first time; the board
        ignores them after, so a panel someone dragged stays dragged and one
        somebody moved to another page stays moved. A ``description`` is the
        note only sessions read, and is left alone when it is not given.

        Naming no page is not the same as naming the page that is showing. A
        panel that names none is born on the board's default page, because what
        happened to be up the moment a panel was first written has nothing to do
        with where that panel belongs.
        """
        body: dict = {"payload": payload, **place}
        if description:
            body["description"] = description
        if page:
            body["page"] = page
        self.call("PUT", f"/board/items/by-key/{key}", body)


def tick(board: Board, sources: list[Source], state: Path, now: float) -> None:
    """Run every source that is due."""
    for source in sources:
        if now < source.due:
            continue
        source.due = now + source.every
        if source.kind == JOB:
            source.start(state)
            continue
        if not source.runs:
            # A static widget: nothing to run, it only has to exist and stay put.
            board.write(source.name, dict(source.spec["panel"]), source.place, page=source.page)
            continue
        produced = read_source(source.spec, state)
        if produced is None:
            continue
        if source.kind == ANNOUNCEMENTS:
            for entry in source.news(produced if isinstance(produced, list) else []):
                board.announce(entry)
            continue
        board.write(source.name, source.payload(produced), source.place, page=source.page)


def configured(given: Path | None) -> Path:
    """Which sources file to run: this instance's, else the shipped example."""
    if given is not None:
        return given
    return DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else EXAMPLE_CONFIG


def main() -> None:
    """Load the config and keep it running."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--once", action="store_true", help="one pass, then exit")
    args = parser.parse_args()

    declared = Declared(configured(args.config))
    if not declared.refresh():
        sys.exit(f"no sources to run from {declared.path}")

    board = Board(args.api)
    state = declared.path.parent
    while True:
        tick(board, declared.refresh(), state, time.monotonic())
        if args.once:
            return
        time.sleep(1)


if __name__ == "__main__":
    main()
