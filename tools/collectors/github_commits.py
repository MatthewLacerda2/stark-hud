#!/usr/bin/env python3
"""Recent commits of yours, as JSON entries for a feed widget.

Goes through `gh`, which is already logged in on this machine, so no token is
stored here. Standard library plus that one subprocess, like every other
collector.

This asks the commit search who wrote what, rather than reading the events
feed, and the events feed is why. It is documented as best-effort and behaves
like it: an evening of commits sat on the default branch while the feed listed
nothing newer than that morning, and the board went stale with nothing failing
anywhere — no error to catch, no retry that helps. Search answers the question
the board is actually asking, and carries the message, so a pass costs one call
rather than one per push.

Only your own public activity, which `is:public` is there to keep true. Search
sees whatever the authenticated user sees, private repositories included, and
work commits on the board were weighed once and decided against: that route is
an employer's business rather than a living room's.

Nothing is remembered between runs. It asks for the last N commits every time
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
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"gh api {path}: {exc}", file=sys.stderr)
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def entries(found: object) -> list[dict]:
    """Feed entries out of what the commit search answered.

    Every field is reached for defensively rather than indexed: this is
    somebody else's JSON, and one commit missing a committer should cost that
    line and not the whole panel.
    """
    items = found.get("items") if isinstance(found, dict) else None
    if not items:
        return []

    shaped = []
    for item in items:
        commit = item.get("commit") or {}
        message = commit.get("message") or ""
        repo = (item.get("repository") or {}).get("name") or ""
        # The committer's date, not the author's: a rebased commit keeps the
        # date it was written, which on a feed reads as time travel.
        at = (commit.get("committer") or {}).get("date")
        if not message or not at:
            continue
        shaped.append({"title": message.split("\n")[0], "source": repo, "at": at})
    return shaped


def commits(user: str, limit: int) -> list[dict]:
    """Your public commits, newest first, whatever repository they landed in."""
    # Ordered by committer date rather than by relevance, which is what search
    # gives you otherwise and is not a feed.
    query = f"author:{user}+is:public"
    return entries(gh(f"/search/commits?q={query}&sort=committer-date&order=desc&per_page={limit}"))


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

    feed = commits(user, args.limit)

    if not feed:
        # Better to fail than to print an empty feed: the agent leaves the last
        # good contents on the board instead of blanking it over a hiccup.
        print("no commits found", file=sys.stderr)
        return 1

    print(json.dumps(feed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
