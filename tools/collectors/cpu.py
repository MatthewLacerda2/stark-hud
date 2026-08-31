#!/usr/bin/env python3
"""Busy percentage per core, sampled over a short window (what htop shows)."""

import json
import time
from pathlib import Path

WINDOW_SECONDS = 0.4


def snapshot() -> dict[str, tuple[int, int]]:
    """Total and idle jiffies per core."""
    out: dict[str, tuple[int, int]] = {}
    for line in Path("/proc/stat").read_text().splitlines():
        if not line.startswith("cpu") or line.startswith("cpu "):
            continue
        parts = line.split()
        values = [int(v) for v in parts[1:]]
        out[parts[0]] = (sum(values), values[3] + values[4])
    return out


first = snapshot()
time.sleep(WINDOW_SECONDS)
second = snapshot()

rows = []
for core, (total2, idle2) in second.items():
    total1, idle1 = first[core]
    d_total, d_idle = total2 - total1, idle2 - idle1
    busy = 0.0 if d_total <= 0 else round((1 - d_idle / d_total) * 100, 1)
    rows.append({"core": core.removeprefix("cpu"), "use": busy})

print(json.dumps(rows))
