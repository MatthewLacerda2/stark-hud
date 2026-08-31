#!/usr/bin/env python3
"""One GPU reading as a gauge row.

    gpu.py util   how busy the chip is
    gpu.py vram   how full its memory is, with the gigabytes in the label

One metric per call because a gauge shows one number; the caller decides which.
"""

import json
import subprocess
import sys

QUERY = "utilization.gpu,memory.used,memory.total"
mode = sys.argv[1] if len(sys.argv) > 1 else "util"

try:
    out = subprocess.run(
        ["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout.splitlines()[0]
except (OSError, subprocess.SubprocessError, IndexError) as exc:
    sys.exit(f"nvidia-smi unavailable: {exc}")

util, used, total = (float(v) for v in out.split(","))

if mode == "vram":
    row = {"label": f"{used / 1024:.1f} de {total / 1024:.0f} GB",
           "pct": round(used / total * 100, 1)}
else:
    row = {"label": "uso", "pct": util}

print(json.dumps([row]))
