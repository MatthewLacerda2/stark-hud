#!/usr/bin/env python3
"""Memory as one gauge row: percentage for the arc, gigabytes for the label."""

import json
from pathlib import Path

TO_GB = 1024 * 1024


def parse(meminfo: str) -> dict[str, int]:
    """Every field of /proc/meminfo, in kilobytes."""
    fields: dict[str, int] = {}
    for line in meminfo.splitlines():
        key, _, rest = line.partition(":")
        fields[key] = int(rest.split()[0])
    return fields


def row(fields: dict[str, int]) -> dict[str, object]:
    """What is in use, as the gauge wants it.

    `MemAvailable` rather than `MemFree`, because free memory on Linux is not
    memory you can have: the cache counts as available and reading it as used
    puts every idle machine at ninety per cent.
    """
    total = fields["MemTotal"]
    used = total - fields.get("MemAvailable", fields["MemFree"])
    return {
        # Empty: the gauge shows an icon and its ring, nothing written.
        # ``size`` keeps the figure on the board for whoever reads it back.
        "label": "",
        "size": f"{used / TO_GB:.1f}/{total / TO_GB:.1f} GB",
        "use": round(used / total * 100, 1),
    }


def main() -> None:
    """Read the counters and print one row."""
    print(json.dumps([row(parse(Path("/proc/meminfo").read_text()))]))


if __name__ == "__main__":
    main()
