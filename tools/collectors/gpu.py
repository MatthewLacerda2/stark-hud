#!/usr/bin/env python3
"""GPU load and memory, the way nvtop reads them."""

import json
import subprocess
import sys

QUERY = "utilization.gpu,memory.used,memory.total"

try:
    out = subprocess.run(
        ["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout.splitlines()[0]
except (OSError, subprocess.SubprocessError, IndexError) as exc:
    sys.exit(f"nvidia-smi unavailable: {exc}")

util, used, total = (float(v) for v in out.split(","))
print(json.dumps([
    {"metric": "uso", "pct": util},
    {"metric": f"vram {used / 1024:.1f}/{total / 1024:.0f} GB", "pct": round(used / total * 100, 1)},
]))
