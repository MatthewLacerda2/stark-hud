#!/usr/bin/env python3
"""One GPU reading as a gauge row.

    gpu.py util   how busy the chip is
    gpu.py vram   how full its memory is, with the gigabytes in the label

One metric per call because a gauge shows one number; the caller decides which.
"""

import fcntl
import json
import subprocess
import sys
from pathlib import Path

QUERY = "utilization.gpu,memory.used,memory.total"
mode = sys.argv[1] if len(sys.argv) > 1 else "util"

# One nvidia-smi at a time, across both metrics and every run.
#
# A timeout is not enough. When the driver wedges, nvidia-smi goes into
# uninterruptible sleep: the timeout fires, the kill is queued, and the process
# stays anyway. Two of these every three seconds put sixty unkillable processes
# on the machine and the load average past sixty, which was felt as the screen
# freezing. Holding a lock means a wedged driver costs one stuck process, not a
# new one per tick.
LOCK = Path("/tmp/stark-hud-nvidia-smi.lock")  # noqa: S108 - a lock, not data

lock = LOCK.open("w")
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit("nvidia-smi is already running and has not come back")

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
    # No reading line: "uso" was a word where a number should be, and the ring
    # already says how much. The gauge draws nothing when the label is empty.
    row = {"label": "", "pct": util}

print(json.dumps([row]))
