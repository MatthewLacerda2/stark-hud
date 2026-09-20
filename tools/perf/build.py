"""Getting two bundles to compare, without disturbing the checkout you are in.

The working tree builds in place — `frontend/dist` is build output and nobody
misses it. A reference builds in a detached git worktree of its own under the
rig's scratch directory, so `master` can be measured from a branch without
anybody checking anything out.

`node_modules` is borrowed rather than installed, for the reason the `Makefile`
already gives: a fresh worktree's own `bun install` is 430 packages and 356 MB
of tmpfs for a tree byte-identical to the one next door, on the machine whose
load is the thing that makes measurements lie. It is borrowed only while the
lockfile and `package.json` match, so a reference that changed a dependency
installs its own and is still correct.
"""

from __future__ import annotations

import filecmp
import shutil
import subprocess
from pathlib import Path


class BuildFailed(RuntimeError):
    """A bundle would not build, so there is nothing to measure."""


def _run(argv: list[str], cwd: Path) -> None:
    done = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise BuildFailed(
            f"{' '.join(argv)} in {cwd}:\n{done.stdout[-2000:]}\n{done.stderr[-2000:]}"
        )


def _modules(frontend: Path, lender: Path) -> None:
    """Put a `node_modules` in place: borrowed if it can be, installed if not."""
    here = frontend / "node_modules"
    theirs = lender / "node_modules"
    same = (
        theirs.is_dir()
        and frontend != lender
        and filecmp.cmp(frontend / "bun.lock", lender / "bun.lock", shallow=False)
        and filecmp.cmp(frontend / "package.json", lender / "package.json", shallow=False)
    )
    if same:
        if not here.is_symlink():
            shutil.rmtree(here, ignore_errors=True)
            here.symlink_to(theirs)
        return
    if here.is_symlink():
        here.unlink()
    _run(["bun", "install"], frontend)


def build(frontend: Path, lender: Path) -> Path:
    """Build this frontend and return its `dist`."""
    _modules(frontend, lender)
    _run(["bun", "run", "build"], frontend)
    dist = frontend / "dist"
    if not (dist / "index.html").exists():
        raise BuildFailed(f"{dist} has no index.html after a build that said it worked")
    return dist


def checkout(repo: Path, ref: str, into: Path) -> Path:
    """A detached worktree of `ref`, for building and then throwing away."""
    _run(["git", "worktree", "add", "--detach", str(into), ref], repo)
    return into


def discard(repo: Path, tree: Path) -> None:
    """Take the worktree back out, so `git worktree list` does not fill with rigs."""
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(tree)],
        cwd=repo,
        capture_output=True,
        check=False,
    )


def describe(repo: Path, ref: str) -> str:
    """What a ref actually is right now, so a run can be quoted against a commit."""
    done = subprocess.run(
        ["git", "rev-parse", "--short", ref], cwd=repo, capture_output=True, text=True, check=False
    )
    return done.stdout.strip() or ref
