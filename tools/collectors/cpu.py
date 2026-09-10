#!/usr/bin/env python3
"""Busy percentage per core, sampled over a short window (what htop shows)."""

import json
import time
from pathlib import Path

WINDOW_SECONDS = 0.4

# Where the kernel publishes what shares a physical core with what.
CPUS = Path("/sys/devices/system/cpu")

Jiffies = dict[str, tuple[int, int]]


def parse(stat: str) -> Jiffies:
    """Total and idle jiffies per core, out of the text of /proc/stat.

    The aggregate `cpu ` line is skipped: it is the sum of the others, and a
    bar for "all of them at once" beside the per-core bars reads as one more
    core that is somehow always average.
    """
    out: Jiffies = {}
    for line in stat.splitlines():
        if not line.startswith("cpu") or line.startswith("cpu "):
            continue
        parts = line.split()
        values = [int(v) for v in parts[1:]]
        out[parts[0]] = (sum(values), values[3] + values[4])
    return out


def busy(first: Jiffies, second: Jiffies) -> list[dict[str, object]]:
    """How busy each core was between two readings, as chart rows.

    A window with no jiffies in it at all reads as idle rather than as a
    division by zero: it means nothing happened, which is what 0% says.
    """
    rows: list[dict[str, object]] = []
    for core, (total2, idle2) in second.items():
        total1, idle1 = first[core]
        spent, idled = total2 - total1, idle2 - idle1
        used = 0.0 if spent <= 0 else round((1 - idled / spent) * 100, 1)
        rows.append({"core": core.removeprefix("cpu"), "use": used})
    return rows


def siblings() -> dict[str, str]:
    """Which physical core each logical core sits on, as the kernel spells it.

    The value is whatever `thread_siblings_list` said — "0,4" for both of the
    threads sharing one core on this machine — so two threads of the same core
    come back under the same string and nothing downstream has to parse it.

    Empty where there is no topology to read, which is what a container or a
    machine without SMT looks like. Every core is then its own group, and the
    order is the one it already had.
    """
    out: dict[str, str] = {}
    for path in sorted(CPUS.glob("cpu[0-9]*/topology/thread_siblings_list")):
        try:
            out[path.parent.parent.name.removeprefix("cpu")] = path.read_text().strip()
        except OSError:
            continue
    return out


def paired(rows: list[dict[str, object]], groups: dict[str, str]) -> list[dict[str, object]]:
    """Rows reordered so the two threads of one physical core are neighbours.

    This is what decides whether the radar means anything. The rows go round the
    ring in the order they are given, and this machine enumerates the threads of
    a core as 0 and 4 — four spokes apart on an octagon, which is exactly
    opposite. Left alone, one busy core draws as two thin spikes on opposite
    sides of the circle and the shape reads as noise. Side by side, the same
    load is one fat lobe, which is the whole reading.

    It lives here rather than in the widget because only this machine can see
    its own topology, and the collector is already what decides what a row is.

    Groups keep the order their first thread appeared in, so the physical cores
    stay in kernel order and only the threads inside one move.
    """
    ring: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        core = str(row["core"])
        ring.setdefault(groups.get(core, core), []).append(row)
    return [row for group in ring.values() for row in group]


def read() -> str:
    """The kernel's counters, right now."""
    return Path("/proc/stat").read_text()


def main() -> None:
    """Sample twice, print the difference, ordered for the ring."""
    first = parse(read())
    time.sleep(WINDOW_SECONDS)
    print(json.dumps(paired(busy(first, parse(read())), siblings())))


if __name__ == "__main__":
    main()
