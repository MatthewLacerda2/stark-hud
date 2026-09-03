#!/usr/bin/env python3
"""One temperature reading, for a series the agent accumulates.

Prints a single row on purpose: `history` in the agent config turns it into a
line, so this never has to remember anything between runs.
"""

import fcntl
import json
import subprocess
import time
from pathlib import Path

# The chips that report a package temperature. Every hwmon on the machine has a
# `temp1_input`; most of them are a disk or a network card, and the board wants
# the one number a person would call "the CPU temperature".
PACKAGE = {"k10temp", "coretemp", "zenpower"}

LOCK = Path("/tmp/stark-hud-nvidia-smi.lock")  # noqa: S108 - a lock, not data


def milli(reading: str) -> float:
    """A hwmon reading, which is in thousandths of a degree, as degrees."""
    return int(reading) / 1000


def cpu_celsius() -> float | None:
    """Package temperature, from whichever hwmon exposes one."""
    for hwmon in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
        try:
            if (hwmon / "name").read_text().strip() not in PACKAGE:
                continue
            return milli((hwmon / "temp1_input").read_text())
        except (OSError, ValueError):
            continue
    return None


def gpu_celsius() -> float | None:
    """GPU temperature from nvidia-smi, if there is one.

    Behind the same lock as the gauges. A wedged driver leaves nvidia-smi in
    uninterruptible sleep where a timeout cannot reach it, so the only defence
    is to never start a second one.
    """
    lock = LOCK.open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None

    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.splitlines()[0]
        return float(out)
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return None


def row(cpu: float | None, gpu: float | None, at: str) -> dict[str, float | str]:
    """One sample. A reading that could not be taken is left out, not zeroed.

    A zero on this chart is a cold CPU, which is a lie; a missing key is a gap
    in the line, which is the truth.
    """
    sample: dict[str, float | str] = {"t": at}
    if cpu is not None:
        sample["cpu"] = cpu
    if gpu is not None:
        sample["gpu"] = gpu
    return sample


def main() -> None:
    """Take one reading and print it."""
    print(json.dumps(row(cpu_celsius(), gpu_celsius(), time.strftime("%H:%M:%S"))))


if __name__ == "__main__":
    main()
