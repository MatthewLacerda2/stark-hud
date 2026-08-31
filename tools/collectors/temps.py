#!/usr/bin/env python3
"""One temperature reading, for a series the agent accumulates.

Prints a single row on purpose: `history` in the agent config turns it into a
line, so this never has to remember anything between runs.
"""

import json
import subprocess
import time
from pathlib import Path


def cpu_celsius() -> float | None:
    """Package temperature, from whichever hwmon exposes one."""
    for hwmon in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
        try:
            name = (hwmon / "name").read_text().strip()
            if name not in {"k10temp", "coretemp", "zenpower"}:
                continue
            return int((hwmon / "temp1_input").read_text()) / 1000
        except (OSError, ValueError):
            continue
    return None


def gpu_celsius() -> float | None:
    """GPU temperature from nvidia-smi, if there is one."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.splitlines()[0]
        return float(out)
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return None


row: dict[str, float | str] = {"t": time.strftime("%H:%M:%S")}
if (cpu := cpu_celsius()) is not None:
    row["cpu"] = cpu
if (gpu := gpu_celsius()) is not None:
    row["gpu"] = gpu

print(json.dumps(row))
