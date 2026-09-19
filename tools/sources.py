#!/usr/bin/env python3
"""The sources file, and what one declared source is.

Which panels a board has and what feeds them is the instance's data rather than
the board's code, so the file lives in `state/` and is edited far more often
than anything here changes. That is the whole reason this module exists apart
from the loop that runs it: the file is re-read whenever it changes on disk, a
file that will not load leaves the last good set running, and a source that is
still going keeps what it had learned.

Standard library only, like the rest of `tools/`.
"""

import json
import os
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent

# What a source does with what it produces. The config never names one: it says
# which by what it carries, and `Source` works it out once.
PANEL, ANNOUNCEMENTS, JOB = "panel", "announcements", "job"

Row = dict[str, Any]


def expand(command: str, state: Path) -> str:
    """A command as the config wrote it, with the paths it cannot know filled in.

    `{collectors}` is the kit that ships with the board, `{state}` the directory
    the sources file itself lives in — which is where this instance's own
    scripts sit. Neither is knowable to whoever wrote the config, and the agent
    may be started from any working directory.
    """
    return command.format(collectors=TOOLS / "collectors", state=state)


def child_env() -> dict[str, str]:
    """The environment every command the agent runs is given.

    A script in `state/` belongs to this instance and can work out everything
    about itself except where the board's kit was checked out to. Handed that,
    it can `from agent import Board` rather than keep a second copy of the
    client — which is how the copy in `board_images.py` came to drift.
    """
    return {**os.environ, "STARK_HUD_TOOLS": str(TOOLS)}


# Split in two on purpose. `fetch` is where the machine is touched — a
# subprocess, a socket — and can only really be exercised by having the machine
# there. `interpret` is where the answer is shaped, takes a string and returns a
# value, and is the half that has actually had the bugs in it.
def fetch(source: dict, state: Path) -> str | None:
    """Run a source and return what it printed, or None if it failed.

    A command prints on stdout, a URL answers with a body. A source with
    neither never reaches here: it is a static widget, and the loop writes it
    without running anything.
    """
    if "command" in source:
        try:
            return subprocess.run(
                expand(source["command"], state),
                shell=True,
                capture_output=True,
                text=True,
                timeout=source.get("timeout", 20),
                check=True,
                env=child_env(),
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"  ! {source['name']}: {exc}", file=sys.stderr)
            return None
    try:
        with urllib.request.urlopen(source["url"], timeout=10) as response:
            return response.read().decode()
    except (urllib.error.HTTPError, OSError) as exc:
        print(f"  ! {source['name']}: {exc}", file=sys.stderr)
        return None


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


def read_source(source: dict, state: Path) -> list[Row] | str | None:
    """Run a source and shape what it produced, or None if either half failed."""
    out = fetch(source, state)
    return None if out is None else interpret(out, source.get("json_path", ""), source["name"])


def _mark(row: Row) -> str:
    """What makes this announcement the same announcement as last time."""
    return str(row.get("key") or row.get("title", ""))


def fault(spec: dict) -> str | None:
    """Why this source cannot be run, or None if it can.

    Checked when the file is read rather than when the source next comes due, so
    a mistake is a line in the log at the moment it is saved instead of a panel
    that quietly stops somewhere in the next five minutes.
    """
    name = spec.get("name")
    if not name:
        return "a source with no name"
    # Presence, not truth: `panel = {}` is a panel, and a source declaring
    # nothing at all is the mistake worth catching.
    if not ("panel" in spec or "command" in spec or spec.get("notifications")):
        return f"{name}: no panel, nothing to run, and nothing to announce"
    if "panel" not in spec and "command" not in spec:
        return f"{name}: announces or works, but has no command"
    return None


class Source:
    """One declared source: what it does with what it produces, and when it is due.

    Three kinds, and the config picks one by what it leaves out rather than by
    naming it:

      panel          has a `panel`. One widget, rewritten every time it runs;
                     with no command or url it is a static widget that only has
                     to exist and stay put.
      announcements  `notifications = true`. The rows are inbox entries, already
                     shaped, so there is no panel and nowhere to put one.
      job            a command and no panel. Something that writes to the board
                     itself — a watcher in `state/` — which the agent starts and
                     does not wait for.
    """

    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.name: str = spec["name"]
        self.every: float = float(spec.get("every", 30))
        self.place: dict = spec.get("place", {})
        self.due = 0.0
        self.runs = "command" in spec or "url" in spec
        self.kind = (
            ANNOUNCEMENTS if spec.get("notifications") else PANEL if "panel" in spec else JOB
        )
        # `history = N` turns a one-row source into a series: the agent keeps the
        # last N samples so a collector never has to remember anything.
        depth = int(spec.get("history", 0))
        self.history: deque[Row] | None = deque(maxlen=depth) if depth else None
        # What was true last time this ran. Not what has ever been said: a
        # condition that clears and comes back is news again, and remembering it
        # forever would silence the second time a disk filled up.
        self.said: set[str] = set()
        self.process: subprocess.Popen | None = None

    def remember(self, old: "Source | None") -> "Source":
        """Take over from the source of this name the last config declared.

        What a reload must not do is undo the running. A saved file should not
        blank a chart that has been filling for an hour, announce a full disk
        that was announced already, or start a second copy of a job halfway
        through rendering. A source whose declaration did not change keeps its
        place in the schedule too, so editing one line does not make every other
        source run again.
        """
        if old is None:
            return self
        self.said = set(old.said)
        self.process = old.process
        if self.history is not None and old.history is not None:
            self.history.extend(old.history)
        if old.spec == self.spec:
            self.due = old.due
        return self

    def start(self, state: Path) -> None:
        """Run this job beside the agent, unless the last one is still going.

        Not waited for. A job can take minutes — rendering a figure, say — and
        the panels have to keep moving while it does. Its output is the agent's
        own, so whatever it prints lands in the same log.
        """
        if self.process is not None and self.process.poll() is None:
            return
        self.process = subprocess.Popen(
            expand(self.spec["command"], state), shell=True, env=child_env()
        )

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


def _stamp(path: Path) -> tuple[int, int] | None:
    """What tells one version of the file from the next, or None if it is gone."""
    try:
        info = path.stat()
    except OSError:
        return None
    return info.st_mtime_ns, info.st_size


class Declared:
    """The sources as the file on disk currently declares them.

    Re-read whenever it changes, because a source change is an edit to a file
    and not a restart of anything: the board keeps being fed while somebody is
    still deciding what to feed it. Anything that will not load — half a save, a
    typo, a source with nothing to run — leaves the last good set running and
    says why, since a broken file should cost a line in the log rather than a
    blank television.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.sources: list[Source] = []
        self.seen: tuple[int, int] | None = None

    def refresh(self) -> list[Source]:
        """The sources to run now, re-reading the file if it has moved on."""
        stamp = _stamp(self.path)
        if stamp == self.seen:
            return self.sources
        self.seen = stamp
        if stamp is None:
            print(f"  ! {self.path} is gone — keeping its sources", file=sys.stderr)
            return self.sources
        declared = self._parse()
        if declared is not None:
            was = {source.name: source for source in self.sources}
            self.sources = [Source(spec).remember(was.get(spec["name"])) for spec in declared]
            print(f"{len(self.sources)} sources from {self.path}", flush=True)
        return self.sources

    def _parse(self) -> list[dict] | None:
        """Every source in the file, or None if the file is not usable.

        All or nothing: one unusable source rejects the whole save it arrived
        in. The alternative is a board running half of what the file says, which
        is the hardest kind of wrong to notice from the sofa.
        """
        try:
            declared = tomllib.loads(self.path.read_text()).get("source", [])
        except (OSError, tomllib.TOMLDecodeError) as exc:
            print(f"  ! {self.path}: {exc}", file=sys.stderr)
            return None
        faults = [problem for problem in map(fault, declared) if problem]
        if not declared:
            faults = [f"no sources declared in {self.path}"]
        for problem in faults:
            print(f"  ! {problem}", file=sys.stderr)
        return None if faults else declared
