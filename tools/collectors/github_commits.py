#!/usr/bin/env python3
"""Recent commits of yours, as JSON entries for a feed widget.

Goes through `gh`, which is already logged in on this machine, so no token is
stored here. Standard library plus that one subprocess, like every other
collector.

This asks the commit search for `author:you` rather than reading the events
feed, and the events feed is why. It is documented as best-effort and behaves
like it: an afternoon of pushes to this repository never appeared in it while
the commits sat plainly on the default branch, and the board went stale with
nobody at fault. Search is authoritative, carries the message so there is no
second call per commit, and orders by committer date.

It also settles a thing that was solved by deletion once. Organisation feeds
were supported and then taken out, because that route is the organisation's
dashboard rather than yours and because naming an organisation means writing an
employer down. Searching by author needs neither: private repositories come
along because the search sees what the authenticated user sees.

Nothing is remembered between runs. It asks for the last N pushes every time
and prints them all, so there is no cursor to lose and a restart changes
nothing — the same lesson the panels themselves learned.

    github_commits.py --limit 10
"""

import argparse
import json
import subprocess
import sys


def gh(path: str) -> object | None:
    """One `gh api` call, or None if it failed."""
    try:
        out = subprocess.run(
            ["gh", "api", path],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"gh api {path}: {exc}", file=sys.stderr)
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def commits(user: str, limit: int) -> list[dict]:
    """Your commits, newest first, whatever repository they landed in."""
    # Search rather than the events feed, which is documented as best-effort and
    # behaves like it: a whole afternoon of pushes to this very repository never
    # appeared in it, while the commits were plainly on the default branch. It
    # also drops one call per push, because a search result carries the message
    # and an event carries only the head sha.
    #
    # `author` is the account, so nothing here names a repository or an
    # organisation. Private repositories come along because the search sees what
    # the authenticated user sees — which is how work commits reach the board
    # without an employer's name being written down anywhere.
    query = f"author:{user}"
    found = gh(f"/search/commits?q={query}&sort=committer-date&order=desc&per_page={limit}")
    items = found.get("items") if isinstance(found, dict) else None
    if not items:
        return []

    entries = []
    for item in items:
        commit = item.get("commit") or {}
        message = commit.get("message") or ""
        repo = (item.get("repository") or {}).get("name") or ""
        at = (commit.get("committer") or {}).get("date")
        if not message or not repo or not at:
            continue
        entries.append({"title": message.split("\n")[0], "source": repo, "at": at})
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", help="defaults to whoever gh is logged in as")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    user = args.user
    if not user:
        who = gh("/user")
        user = who.get("login") if isinstance(who, dict) else None
    if not user:
        print("no GitHub user: is gh logged in?", file=sys.stderr)
        return 1

    entries = commits(user, args.limit)

    if not entries:
        # Better to fail than to print an empty feed: the agent leaves the last
        # good contents on the board instead of blanking it over a hiccup.
        print("no commits found", file=sys.stderr)
        return 1

    print(json.dumps(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
