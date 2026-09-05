#!/usr/bin/env python3
"""What this machine would say if it could interrupt.

Not a panel. These are announcements, and the agent posts each one into the
board's inbox — so a line here has to be worth somebody on a sofa looking up.
Something is wrong, or something changed. A reading that is always true belongs
on a gauge, where it can be ignored.

Every row carries a `key`, and the agent strips it before posting: it is how the
agent knows it has already said this. A key must not move when the number in the
title does, or "3 updates" and "4 updates" are two announcements about one fact.

Standard library only and read-only throughout — this inspects the machine, it
never touches it.
"""

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Above this a disk is worth mentioning. Below it, the gauges already say so.
FULL_AT = 85

# Filesystems that are memory wearing a disk's clothes. A tmpfs at 100% is
# normal and says nothing about the machine.
PSEUDO = frozenset({"tmpfs", "devtmpfs", "efivarfs", "squashfs", "overlay", "ramfs"})


def failed(listing: str, scope: str) -> list[dict]:
    """One row per failed unit, from `systemctl --failed --no-legend`."""
    rows = []
    for line in listing.splitlines():
        unit = line.split()[0] if line.split() else ""
        if not unit.endswith((".service", ".timer", ".mount", ".socket", ".target")):
            continue
        rows.append(
            {
                "key": f"failed:{scope}:{unit}",
                "title": f"{unit} has failed",
                "body": f"A {scope} unit is in the failed state. `systemctl {scope} status {unit}`.",
                "icon": "x-circle",
                "level": "error",
            }
        )
    return rows


def full(listing: str, limit: int = FULL_AT) -> list[dict]:
    """One row per real filesystem past `limit`, from `df -PT`."""
    rows = []
    for line in listing.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 7 or parts[1] in PSEUDO:
            continue
        used = int(parts[5].rstrip("%"))
        if used < limit:
            continue
        rows.append(
            {
                # No percentage in the key: a disk filling further is the same
                # news, and should not announce itself again at every point.
                "key": f"full:{parts[6]}",
                "title": f"{parts[6]} is {used}% full",
                "body": f"{parts[4]} of {parts[2]} blocks free on {parts[0]}.",
                "icon": "hard-drive",
                "level": "error" if used >= 95 else "warn",
            }
        )
    return rows


def stale_kernel(running: str, installed: list[str]) -> list[dict]:
    """A row when the running kernel is no longer on disk.

    The usual shape of this on a rolling release: the kernel was upgraded, the
    old modules were removed, and anything that wants to load one now cannot.
    The machine keeps working and gets stranger until it is restarted.
    """
    if not running or running in installed:
        return []
    return [
        {
            "key": "reboot",
            "title": "A restart is pending",
            "body": f"Running {running}, which is no longer installed. Modules will not load.",
            "icon": "alert-triangle",
            "level": "warn",
        }
    ]


def waiting(listing: str) -> list[dict]:
    """A row when packages are upgradable, from `pacman -Qu`."""
    names = [line.split()[0] for line in listing.splitlines() if line.strip()]
    if not names:
        return []
    return [
        {
            "key": "updates",
            "title": f"{len(names)} packages can be upgraded",
            "body": ", ".join(names[:6]) + ("…" if len(names) > 6 else ""),
            "icon": "download",
            "level": "info",
        }
    ]


def noisy(lines: str, keep: int = 3) -> list[dict]:
    """The loudest sources of journal errors, from `journalctl -p 3 -o json`.

    Grouped rather than one row per error: 24 identical kernel complaints are one
    thing worth knowing, and 24 lines in an inbox is the inbox being useless.
    """
    counts: Counter[str] = Counter()
    last: dict[str, str] = {}
    for line in lines.splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        who = entry.get("_SYSTEMD_UNIT") or entry.get("SYSLOG_IDENTIFIER") or "unknown"
        counts[who] += 1
        last[who] = (entry.get("MESSAGE") or "").strip()[:120]
    return [
        {
            "key": f"errors:{who}",
            "title": f"{who} logged {n} error{'s' if n != 1 else ''}",
            "body": last[who],
            "icon": "bug",
            "level": "warn",
        }
        for who, n in counts.most_common(keep)
    ]


def run(command: list[str]) -> str:
    """What a command printed, or nothing if it could not be run.

    Never raises. A machine without pacman is not a broken collector, it is a
    machine that has nothing to say about pending updates.
    """
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  ! {command[0]}: {exc}", file=sys.stderr)
        return ""
    return done.stdout


def main() -> None:
    """Ask the machine everything, and print what is worth saying."""
    modules = Path("/usr/lib/modules")
    rows = [
        *failed(run(["systemctl", "--failed", "--no-legend", "--plain"]), "system"),
        *failed(run(["systemctl", "--user", "--failed", "--no-legend", "--plain"]), "user"),
        *stale_kernel(
            run(["uname", "-r"]).strip(),
            sorted(p.name for p in modules.iterdir()) if modules.is_dir() else [],
        ),
        *full(run(["df", "-PT"])),
        *waiting(run(["pacman", "-Qu"])),
        *noisy(run(["journalctl", "-p", "3", "--since", "-6h", "-o", "json", "--no-pager"])),
    ]
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
