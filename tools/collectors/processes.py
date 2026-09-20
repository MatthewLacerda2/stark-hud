#!/usr/bin/env python3
"""Who is actually using this machine, one row per program.

Rows are grouped by program name rather than by pid, because "chromium" is the
answer to "what is eating my memory" and "fifty chromium processes" is not. A
browser, a compiler and a training run each split themselves across children,
and a table that lists the children is a table nobody can read from a sofa.

Ordered by the larger of its two memories, each as a fraction of the pool it
comes from: a run holding 5.5 GB of a 6 GB card outranks an editor holding 6 GB
of 32, which is the order somebody looking for the heavy thing wants. RAM and
VRAM usually agree on who is heaviest, and where they disagree the bigger claim
is the interesting one.

Standard library only and read-only throughout: this reads /proc and asks
nvidia-smi, and never touches either.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict

from gpu import take

# Memory shared between processes counted once, not once per child. The kernel
# only offers it for processes we may inspect; for the rest we fall back to RSS,
# which over-counts a shared library per child but is never far wrong for the
# single big consumer this table is looking for.
PSS = "smaps_rollup"

# How long to wait for the one nvidia-smi anybody on this machine may be
# running. The lock and the reason for it are `collectors/gpu.py`'s: a wedged
# driver leaves nvidia-smi unkillable, so a second must never start beside a
# stuck first. The gauges hold it for well under a second, so waiting is almost
# always cheaper than skipping — but unlike a gauge, a table missing its GPU
# column is still a useful table, so giving up costs a column and not the run.
LOCK_WAIT = 2.0

# Where the previous run's CPU counters wait. CPU time is a running total, so a
# percentage needs two readings; keeping the last one here means the figure
# covers the whole gap between refreshes instead of a blink inside one run.
CACHE = Path.home() / ".cache" / "stark-hud" / "proc-cpu.json"

TICKS = os.sysconf("SC_CLK_TCK")
PAGE = os.sysconf("SC_PAGE_SIZE")
CORES = os.cpu_count() or 1

# `comm` is the kernel's name for a process and is the right one almost always —
# it is what the program calls itself. Its one flaw is that it is cut to this
# many characters, and that is the only case worth consulting the executable
# for: `claude` lives at `…/versions/2.1.278`, so the path is the worse name
# whenever `comm` is not truncated.
COMM_MAX = 15


class Proc(TypedDict):
    """One process as `sample` read it: who it is, and the two totals it carries."""

    pid: str
    name: str
    # CPU time since this process started, in kernel ticks. A total, not a rate:
    # the rate is the difference between two runs of this collector.
    ticks: int
    ram: int


def named(pid: str, comm: str) -> str:
    """The program's name, taken from its executable only when the kernel cut it short.

    A cut name is worse than the executable's twice over: `dart:frontend_s` is
    not a word, and the several `dart:` workers of one program are cut to
    different stumps and so land in different rows. Whereas `claude` runs from
    `…/versions/2.1.278`, so for a name that was not cut the path is the worse
    of the two, and it is never consulted.
    """
    if len(comm) < COMM_MAX:
        return comm
    try:
        from_path = os.path.basename(os.readlink(f"/proc/{pid}/exe"))
    except OSError:
        return comm
    # A directory named for a release is a version, not a program.
    return from_path if any(c.isalpha() for c in from_path) else comm


def resident(pid: str) -> int:
    """Bytes of memory this process is holding, shared parts counted fairly."""
    try:
        with open(f"/proc/{pid}/{PSS}") as handle:
            for line in handle:
                if line.startswith("Pss:"):
                    return int(line.split()[1]) * 1024
    except OSError, ValueError, IndexError:
        pass
    try:
        return int(Path(f"/proc/{pid}/statm").read_text().split()[1]) * PAGE
    except OSError, ValueError, IndexError:
        return 0


def counters(pid: str) -> tuple[str, int, int] | None:
    """A process's name, CPU ticks so far, and when it started.

    The start time joins the pid in the cache key. Pids are reused, and a new
    process inheriting the last one's counter would read as a burst of CPU it
    never used.
    """
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        comm = Path(f"/proc/{pid}/comm").read_text().strip()
    except OSError:
        return None
    # The name sits in parentheses and may itself contain spaces and brackets,
    # so the fields after it are found from the last bracket, never by splitting
    # the whole line.
    fields = stat.rpartition(")")[2].split()
    try:
        return named(pid, comm), int(fields[11]) + int(fields[12]), int(fields[19])
    except ValueError, IndexError:
        return None


def sample() -> dict[str, Proc]:
    """Every live process, keyed so a reused pid cannot be mistaken for its predecessor."""
    live: dict[str, Proc] = {}
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        read = counters(entry.name)
        if read is None:
            continue
        name, ticks, started = read
        live[f"{entry.name}:{started}"] = {
            "pid": entry.name,
            "name": name,
            "ticks": ticks,
            "ram": resident(entry.name),
        }
    return live


def previous() -> tuple[dict[str, int], float]:
    """Last run's tick counts and the moment they were taken."""
    try:
        was = json.loads(CACHE.read_text())
        return was["ticks"], float(was["at"])
    except OSError, ValueError, KeyError, TypeError:
        return {}, 0.0


def remember(live: dict[str, Proc], at: float) -> None:
    """Leave this run's counters for the next one. A cache that cannot be written is not an error."""
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps({"at": at, "ticks": {k: v["ticks"] for k, v in live.items()}}))
    except OSError as exc:
        print(f"  ! cache: {exc}", file=sys.stderr)


def vram() -> dict[str, int]:
    """Megabytes of video memory per pid, or nothing if the GPU cannot be asked.

    `pmon` rather than `--query-compute-apps`, which sees only compute clients:
    the desktop and the browser hold video memory as graphics clients and are
    exactly the rows somebody would notice missing.
    """
    # Held until this function returns. `take` hands back the open file *because*
    # the lock lives on it: drop the reference and the flock goes with it.
    until = time.monotonic() + LOCK_WAIT
    lock = take()
    while lock is None:
        if time.monotonic() >= until:
            print("  ! nvidia-smi is busy; no GPU column", file=sys.stderr)
            return {}
        time.sleep(0.1)
        lock = take()
    try:
        printed = subprocess.run(
            ["nvidia-smi", "pmon", "-c", "1", "-s", "m"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  ! nvidia-smi unavailable: {exc}", file=sys.stderr)
        return {}
    return holders(printed)


def holders(printed: str) -> dict[str, int]:
    """Megabytes of video memory per pid, out of what `pmon` printed.

    Columns are gpu, pid, type, fb, ccpm, command, and are read by position:
    the header names them but `pmon` writes no separator, so position is all
    there is. A dash is the driver having no figure for that process, which is
    not the same as a zero and is left out rather than counted as one.
    """
    held: dict[str, int] = {}
    for line in printed.splitlines():
        if line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 4 or not fields[1].isdigit() or not fields[3].isdigit():
            continue
        held[fields[1]] = held.get(fields[1], 0) + int(fields[3])
    return held


def total_ram() -> int:
    """Bytes of memory this machine has, so a share of it can be worked out."""
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except OSError, ValueError, IndexError:
        pass
    return 0


def total_vram() -> int:
    """Bytes of video memory the card has. Zero when there is no card to ask."""
    try:
        printed = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
        return int(float(printed.splitlines()[0])) * 1024 * 1024
    except OSError, subprocess.SubprocessError, ValueError, IndexError:
        return 0


def gigabytes(size: int) -> str:
    """Bytes as somebody would say them, and nothing at all for none."""
    if size <= 0:
        return ""
    if size < 1024**3:
        return f"{size / 1024**2:.0f} MB"
    return f"{size / 1024**3:.1f} GB"


def percent(share: float) -> str:
    """A share of the machine, rounded, and blank rather than a column of zeroes.

    Anything under half a percent is drawn as `<1%`: it is not nothing — it is
    the row still being alive — and a table where most of the column is empty
    reads as broken rather than as quiet.
    """
    if share <= 0:
        return ""
    return f"{share:.0f}%" if share >= 0.5 else "<1%"


def heaviest(
    live: dict[str, Proc],
    held: dict[str, int],
    was: dict[str, int],
    window: float,
    pools: tuple[int, int],
    keep: int,
) -> list[dict[str, object]]:
    """The heaviest programs, one row each, heaviest first.

    Grouped by name here and not by the caller: the sums are what get ordered,
    and ordering the pids first and adding them up after gives a different and
    wrong answer.

    A `window` of zero is the first pass after a restart — no earlier reading to
    subtract, so no CPU figure exists yet and the column is blank for one
    refresh rather than full of nonsense.
    """
    ram_pool, vram_pool = pools
    totals: dict[str, dict[str, float]] = {}
    for token, proc in live.items():
        row = totals.setdefault(proc["name"], {"cpu": 0.0, "ram": 0.0, "vram": 0.0})
        row["ram"] += proc["ram"]
        row["vram"] += held.get(proc["pid"], 0) * 1024 * 1024
        if window:
            spent = proc["ticks"] - was.get(token, proc["ticks"])
            # Only forward. A counter that went backwards is a pid this run read
            # differently, not a program that gave CPU time back.
            row["cpu"] += max(spent, 0) / TICKS / window / CORES * 100

    def weight(item: tuple[str, dict[str, float]]) -> float:
        """The larger of a program's two memories, each against its own pool.

        Against its own pool, not in bytes: a run holding almost all of a 6 GB
        card is the heavy thing on this machine even beside an editor holding
        more gigabytes of a much larger RAM, and in bytes it would sort below it.
        """
        _, row = item
        return max(
            row["ram"] / ram_pool if ram_pool else 0,
            row["vram"] / vram_pool if vram_pool else 0,
        )

    return [
        {
            "name": name,
            "cpu": percent(row["cpu"]),
            "gpu": gigabytes(int(row["vram"])),
            "ram": gigabytes(int(row["ram"])),
        }
        for name, row in sorted(totals.items(), key=weight, reverse=True)[:keep]
    ]


def gather(keep: int) -> list[dict[str, object]]:
    """Read the machine, and shape what it said into rows."""
    at = time.monotonic()
    live = sample()
    was, then = previous()
    remember(live, at)
    return heaviest(
        live,
        vram(),
        was,
        at - then if then and at > then else 0.0,
        (total_ram(), total_vram()),
        keep,
    )


def main() -> None:
    """Print the heaviest programs as the table's rows."""
    keep = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    print(json.dumps(gather(keep)))


if __name__ == "__main__":
    main()
