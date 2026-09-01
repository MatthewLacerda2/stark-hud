#!/usr/bin/env python3
"""Recent commits of yours, as JSON entries for a feed widget.

Goes through `gh`, which is already logged in on this machine, so no token is
stored here and the organisation authorisation that `gh` was granted once keeps
working. Standard library plus that one subprocess, like every other collector.

Two things the GitHub API makes awkward, both learned the hard way:

  * a PushEvent no longer carries its commits — only the head sha — so the
    message costs one extra call per push;
  * `/users/{you}/events` shows public repositories only. Private ones show up
    under `/users/{you}/events/orgs/{org}`, which is why organisations have to
    be named rather than discovered;
  * that organisation route is the *organisation\'s* dashboard, not yours — it
    carries everything in the org you are allowed to see, colleagues included.
    Every event is checked against `actor.login` for that reason.

Nothing is remembered between runs. It asks for the last N pushes every time
and prints them all, so there is no cursor to lose and a restart changes
nothing — the same lesson the panels themselves learned.

    github_commits.py --org TrussInt --org pgbezerra-org --limit 10
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


def pushes(user: str, orgs: list[str], limit: int) -> list[dict]:
    """Every push we can see, newest first, one entry per push."""
    # The largest page the API allows. The organisation feeds are mostly other
    # people's work, and asking for less means your own pushes fall off the end
    # before the filter below ever sees them.
    feeds = [f"/users/{user}/events?per_page=100"]
    feeds += [f"/users/{user}/events/orgs/{org}?per_page=100" for org in orgs]

    seen: dict[str, dict] = {}
    for feed in feeds:
        for event in gh(feed) or []:
            if event.get("type") != "PushEvent":
                continue
            # The organisation feed is the whole org's activity. Without this,
            # the board fills up with your colleagues' work.
            if (event.get("actor") or {}).get("login", "").lower() != user.lower():
                continue
            head = (event.get("payload") or {}).get("head")
            repo = (event.get("repo") or {}).get("name")
            if not head or not repo or head in seen:
                continue
            seen[head] = {"repo": repo, "head": head, "at": event.get("created_at")}

    ordered = sorted(seen.values(), key=lambda e: e["at"] or "", reverse=True)
    return ordered[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", help="defaults to whoever gh is logged in as")
    parser.add_argument("--org", action="append", default=[])
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    user = args.user
    if not user:
        who = gh("/user")
        user = who.get("login") if isinstance(who, dict) else None
    if not user:
        print("no GitHub user: is gh logged in?", file=sys.stderr)
        return 1

    entries = []
    for push in pushes(user, args.org, args.limit):
        commit = gh(f"/repos/{push['repo']}/commits/{push['head']}")
        if not isinstance(commit, dict):
            continue
        message = (commit.get("commit") or {}).get("message") or ""
        entries.append({
            "title": message.split("\n")[0],
            "source": push["repo"].split("/")[-1],
            "at": push["at"],
        })

    if not entries:
        # Better to fail than to print an empty feed: the agent leaves the last
        # good contents on the board instead of blanking it over a hiccup.
        print("no commits found", file=sys.stderr)
        return 1

    print(json.dumps(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
