"""`make perf` — one command, a before/after, and the conditions it was taken under.

Three ways to run it:

    make perf                 what this working tree costs, on its own
    make perf REF=master      this working tree against master, interleaved
    make perf LIVE=1          the television: the four-way split, with a GPU figure

The first two build bundles and drive headless browsers of their own, and print
no GPU number at all, because a headless instance rasters in software: it draws
the board on the CPU and paints the SVG filters black, so its idea of the card
is about a different program. Only `LIVE=1` is measuring the thing in the room.

Every run ends with the picture-unchanged check and with the 2026-09-19
baseline, in that order. The timings say whether a change is cheaper; the
picture check says whether it is allowed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from perf import build, cost, live, sweep
from perf.cdp import version_string

DEFAULT_ROUNDS = 4
DEFAULT_SECONDS = 20.0
# Two ports nothing else on this machine wants, and never 9222: that is the
# kiosk's, and this rig only ever reads from it.
BASE_PORT = 9411


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="perf", description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="the checkout to measure")
    parser.add_argument(
        "--ref",
        action="append",
        default=None,
        help="a git ref to measure this tree against; give it twice for two of them",
    )
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    parser.add_argument("--live", action="store_true", help="measure the running kiosk instead")
    parser.add_argument("--port", type=int, default=9222, help="the kiosk's debugging port")
    parser.add_argument("--page", default=None, help="which page target on that port")
    parser.add_argument("--headful", action="store_true", help="show the browsers (no GPU claim)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse(argv if argv is not None else sys.argv[1:])
    if args.live:
        for line in live.run(args.port, args.seconds, args.page):
            print(line)
        return 0
    return _sweep(args)


def _sweep(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    scratch = Path(tempfile.mkdtemp(prefix="stark-perf-"))
    trees: list[Path] = []
    arms: list[sweep.Arm] = []
    try:
        # Refs first and the working tree last, so the picture check compares
        # everything against the oldest arm - which is the one somebody is
        # asking permission to change.
        plan: list[tuple[str, str | None]] = [(r, r) for r in (args.ref or [])]
        plan.append(("working", None))
        for index, (name, ref) in enumerate(plan):
            frontend, commit = _frontend_for(repo, ref, scratch, trees)
            print(f"building {name} ({commit}) ...")
            dist = build.build(frontend, repo / "frontend")
            # Each arm's build is copied out before the next one is made: two
            # worktrees of the same repository share nothing, but the working
            # tree's own `dist` is one directory and the second build would
            # overwrite the first.
            kept = scratch / f"dist-{index}"
            shutil.copytree(dist, kept)
            arms.append(
                sweep.open_arm(
                    name,
                    commit,
                    kept,
                    BASE_PORT + index,
                    scratch / f"profile-{index}",
                    headless=not args.headful,
                )
            )
        conditions = cost.Conditions(
            where="headless" if not args.headful else "a visible browser on this desktop",
            browser=version_string(BASE_PORT),
            cores=os.cpu_count() or 0,
            load_start=cost.loadavg(),
            gpu_tenants=cost.gpu_tenants(),
        )
        print(
            f"\nsweeping {len(arms)} arm(s), {args.rounds} rounds of {args.seconds:g}s, interleaved\n"
        )
        sweep.run(arms, args.rounds, args.seconds)
        conditions.load_end = cost.loadavg()

        lines = sweep.summarise(arms, conditions)
        picture = ["", "is it the same picture", ""] + [f"  {line}" for line in sweep.picture(arms)]
        for line in lines[:2] + picture + lines[2:]:
            print(line)
    finally:
        for arm in arms:
            arm.close()
        for tree in trees:
            build.discard(repo, tree)
        shutil.rmtree(scratch, ignore_errors=True)
    return 0


def _frontend_for(
    repo: Path, ref: str | None, scratch: Path, trees: list[Path]
) -> tuple[Path, str]:
    """This working tree, or a throwaway checkout of a ref beside it."""
    if ref is None:
        return repo / "frontend", build.describe(repo, "HEAD") + _dirty(repo)
    tree = build.checkout(repo, ref, scratch / f"tree-{ref.replace('/', '-')}")
    trees.append(tree)
    return tree / "frontend", build.describe(repo, ref)


def _dirty(repo: Path) -> str:
    """A working tree with changes in it is not its commit, and must not be quoted as one."""
    done = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=False
    )
    return "+dirty" if done.stdout.strip() else ""


if __name__ == "__main__":
    sys.exit(main())
