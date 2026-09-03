#!/usr/bin/env python3
"""Busy percentage per core, sampled over a short window (what htop shows)."""

import json
import time
from pathlib import Path

WINDOW_SECONDS = 0.4

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


def read() -> str:
    """The kernel's counters, right now."""
    return Path("/proc/stat").read_text()


def main() -> None:
    """Sample twice and print the difference."""
    first = parse(read())
    time.sleep(WINDOW_SECONDS)
    print(json.dumps(busy(first, parse(read()))))


if __name__ == "__main__":
    main()
