#!/usr/bin/env python3
"""Open tmux session names, as a JSON array for a list panel."""

import json
import subprocess


def names(listing: str) -> list[str]:
    """The session names out of what `tmux ls` printed."""
    return [line for line in listing.splitlines() if line]


def read() -> str:
    """Ask tmux. No sessions, or no tmux at all, is not an error here."""
    try:
        return subprocess.run(
            ["tmux", "ls", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> None:
    """Print the open sessions."""
    print(json.dumps(names(read())))


if __name__ == "__main__":
    main()
