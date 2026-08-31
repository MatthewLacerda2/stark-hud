#!/usr/bin/env python3
"""Open tmux session names, as plain text for a note."""

import subprocess

try:
    out = subprocess.run(
        ["tmux", "ls", "-F", "#{session_name}"],
        capture_output=True, text=True, timeout=5, check=True,
    ).stdout
    names = [line for line in out.splitlines() if line]
except (OSError, subprocess.SubprocessError):
    names = []

print("tmux\n\n" + ("\n".join(names) if names else "(nenhuma sessão)"))
