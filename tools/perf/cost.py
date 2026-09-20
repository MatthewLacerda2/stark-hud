"""What a browser costs, measured the two ways that are not lies.

**CPU comes from `/proc/<pid>/stat`, never from `ps`.** `ps %cpu` is the
process's whole life divided by its whole life: a renderer that has been up for
an hour and went twice as fast a minute ago reports almost exactly what it
reported before. It cannot see a change, which is the only thing a rig is for.
`utime + stime` sampled twice and subtracted can.

**`top`'s first sample is the same mistake** and is worth naming because it is
the one people reach for instead: its opening screen is an average since boot,
and only the second refresh describes now. Nothing here shells out to `top`.

**GPU comes from `nvidia-smi`, and on this machine it is the whole card.**
Utilization is not per-process, and this box trains a model on the same GPU the
board draws on. So a GPU number is honest as a *difference between two arms
measured minutes apart*, and dishonest as "what the board costs" unless the
card is otherwise idle — which `Conditions` checks and says.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

CLOCK_TICKS = os.sysconf("SC_CLK_TCK")


def jiffies_in(stat: str) -> int:
    """`utime + stime` out of one line of `/proc/<pid>/stat`.

    The second field is the command name in parentheses, and it may itself
    contain spaces and parentheses — `(Isolated Web Co)` is an ordinary
    chromium process name. So the fields are counted from the *last* ')' and
    never split from the left, which is the bug every reader of this file has
    written at least once. utime and stime are the 14th and 15th overall.
    """
    fields = stat[stat.rindex(")") + 2 :].split()
    return int(fields[11]) + int(fields[12])


def jiffies(pid: int) -> int | None:
    """`utime + stime` for one process, or None if it has gone."""
    try:
        return jiffies_in(Path(f"/proc/{pid}/stat").read_text(encoding="utf-8"))
    except OSError, ValueError, IndexError:
        return None


@dataclass
class Cpu:
    """CPU over a window, as a percentage of one core. 100 % is one core, busy."""

    started: float = 0.0
    before: dict[int, int] = field(default_factory=dict)

    def start(self, pids: list[int]) -> None:
        self.before = {pid: t for pid in pids if (t := jiffies(pid)) is not None}
        self.started = time.monotonic()

    def stop(self, pids: list[int]) -> tuple[float, int]:
        """Percent of a core, and how many processes it was spread over.

        Only processes alive at both ends count. A renderer that appeared
        mid-window has no `before` to subtract from, and charging its whole
        lifetime to this window is exactly the `ps` mistake in another costume.
        """
        elapsed = time.monotonic() - self.started
        total = 0
        counted = 0
        for pid in pids:
            start = self.before.get(pid)
            end = jiffies(pid)
            if start is None or end is None:
                continue
            total += end - start
            counted += 1
        if elapsed <= 0:
            return 0.0, counted
        return 100.0 * (total / CLOCK_TICKS) / elapsed, counted


class Gpu:
    """Card utilization and power, averaged over a window by polling in the background."""

    INTERVAL_S = 0.5

    def __init__(self) -> None:
        self.available = shutil.which("nvidia-smi") is not None
        self._stop = threading.Event()
        self._readings: list[tuple[float, float]] = []
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.available:
            return
        self._readings = []
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def stop(self) -> tuple[float, float] | None:
        """Mean utilization percent and mean power in watts, or None with no card."""
        if not self.available or self._thread is None:
            return None
        self._stop.set()
        self._thread.join(timeout=5)
        if not self._readings:
            return None
        used = sum(r[0] for r in self._readings) / len(self._readings)
        watts = sum(r[1] for r in self._readings) / len(self._readings)
        return used, watts

    def _poll(self) -> None:
        while not self._stop.wait(self.INTERVAL_S):
            reading = _smi("utilization.gpu,power.draw")
            if reading is None:
                continue
            parts = reading.split(",")
            try:
                self._readings.append((float(parts[0]), float(parts[1])))
            except ValueError, IndexError:
                continue


def _smi(query: str) -> str | None:
    if shutil.which("nvidia-smi") is None:
        return None
    done = subprocess.run(
        ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=False,
    )
    return (
        done.stdout.strip().splitlines()[0]
        if done.returncode == 0 and done.stdout.strip()
        else None
    )


def gpu_tenants() -> list[str]:
    """What else is using the card right now, by name. Empty is a quiet card."""
    if shutil.which("nvidia-smi") is None:
        return []
    done = subprocess.run(
        ["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        check=False,
    )
    names = []
    for line in done.stdout.splitlines():
        pid, _, command = line.partition(",")
        if not pid.strip():
            continue
        # The command line of a chromium GPU process is two hundred characters of
        # shared-memory handles. What a reader needs is that somebody else is on
        # the card, and roughly who.
        name = Path(command.strip().split()[0]).name if command.strip() else "?"
        names.append(f"{name} ({pid.strip()})")
    return names


def loadavg() -> tuple[float, float, float]:
    one, five, fifteen = Path("/proc/loadavg").read_text(encoding="utf-8").split()[:3]
    return float(one), float(five), float(fifteen)


@dataclass
class Conditions:
    """Everything a number has to be quoted with to be worth quoting.

    A figure without these compares to nothing. The board runs on a box that is
    eight cores and usually carries a training run; on 2026-09-20 the same
    `bun install` measured 14.4 s under load and 0.75 s on a quiet machine, an
    eighteenfold difference that came entirely from the neighbours. That number
    nearly went into a pull request as a finding.
    """

    where: str
    browser: str
    cores: int
    load_start: tuple[float, float, float]
    load_end: tuple[float, float, float] = (0.0, 0.0, 0.0)
    gpu_tenants: list[str] = field(default_factory=list)

    @property
    def gpu_is_meaningful(self) -> bool:
        """Whether a GPU figure taken here says anything about the television.

        Headless Chromium rasters in software (SwiftShader). It draws the board
        on the CPU, and the board's SVG filters come out black, so both the GPU
        number and the picture are of a different program. The card is also
        shared, so even on the television a figure is only a difference.
        """
        return self.where != "headless"

    @property
    def load_moved(self) -> float:
        return abs(self.load_end[0] - self.load_start[0])

    @property
    def oversubscribed(self) -> bool:
        """More runnable work than there are cores, at either end of the run.

        Interleaving still makes the arms comparable to each other. It does
        nothing for comparing either of them to a figure taken on a quiet box,
        and busy is this machine's normal state rather than its exception.
        """
        return max(self.load_start[0], self.load_end[0]) > self.cores

    def lines(self) -> list[str]:
        out = [
            f"  where        {self.where}",
            f"  browser      {self.browser}",
            f"  machine      {self.cores} cores, "
            f"load {self.load_start[0]:.2f} -> {self.load_end[0]:.2f} (1 min)",
        ]
        if self.gpu_tenants:
            out.append(f"  card shared  {', '.join(self.gpu_tenants[:4])}")
        if self.oversubscribed:
            out.append(f"  caution      the load passed {self.cores} on {self.cores} cores here.")
            out.append("               The arms stay comparable to each other. Neither is")
            out.append("               comparable to a figure taken on a quiet machine.")
        if not self.gpu_is_meaningful:
            out.append(
                "  gpu          not reported: headless rasters in software, so the card is idle"
            )
            out.append(
                "               and the board's SVG filters paint black. Measure GPU with --live."
            )
        return out
