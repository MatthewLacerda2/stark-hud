#!/usr/bin/env python3
"""Memory as one gauge row: percentage for the arc, gigabytes for the label."""

import json
from pathlib import Path

fields = {}
for line in Path("/proc/meminfo").read_text().splitlines():
    key, _, rest = line.partition(":")
    fields[key] = int(rest.split()[0])

total_kb = fields["MemTotal"]
used_kb = total_kb - fields.get("MemAvailable", fields["MemFree"])
to_gb = 1024 * 1024

print(json.dumps([{
    "label": f"{used_kb / to_gb:.1f}/{total_kb / to_gb:.1f} GB",
    "use": round(used_kb / total_kb * 100, 1),
}]))
