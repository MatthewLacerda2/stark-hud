#!/usr/bin/env python3
"""Put the plots of whatever training run owns the GPU on the board.

The TinyRefinementModel repo already draws its own figures — three sheets, one
`make report` away, the same ones anybody reads when deciding something. This
does not redraw them and does not second-guess them. It runs that plotter and
hangs the pictures on the wall.

That is the whole design, and it is deliberate after trying the other way. The
board can draw native charts from data rows, which self-update and look tidy,
but every panel then has to be re-derived from `metrics.csv` and re-decided —
what it plots, what its scale means, what counts as alarming — and the result
was worse than the sheets it was reimplementing. The plots are the product.
This is a picture hook.

    python3 tools/trm_board.py ~/Desktop/Repos/TinyRefinementModel

It runs until stopped. Nobody has to point it at a run: it watches the card, so
the widgets appear when a real run starts and come down an hour after the card
goes quiet.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import itertools
import json
import pathlib
import subprocess
import sys
import time

from board_images import clear, log, measure, show

POLL_SECONDS = 60  # how often the card is looked at
IDLE_SECONDS = 3600  # how long it stays quiet before the widgets come down
REFRESHES_PER_RUN = 20  # how many times a run is redrawn over its whole life
FASTEST, SLOWEST = 300, 3600  # and the bounds on that, in seconds

# A run earns a place on the television when it is the real model, on the card,
# for long enough that watching it means anything. Both numbers are about scale
# and duration; neither looks at what a run is called.
MIN_BUDGET_TOKENS = 20_000_000  # ~1 hour at this box's measured ~5.7k tok/s
MIN_LATENT_DIM = 960  # the shipped width; a toy ablation is narrower

# ── the run that owns the card ───────────────────────────────────────────────


def gpu_pids() -> list[int]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"nvidia-smi unavailable ({exc}) — treating the card as idle")
        return []
    return [int(word) for word in out.split() if word.isdigit()]


def run_dir_of(pid: int) -> pathlib.Path | None:
    """The run a trainer is writing into, from its own command line.

    Reading /proc rather than guessing from file mtimes is what keeps this right
    the moment two run directories exist, which is most of the time.
    """
    try:
        raw = (pathlib.Path("/proc") / str(pid) / "cmdline").read_bytes()
    except OSError:
        return None
    args = [part.decode(errors="replace") for part in raw.split(b"\0") if part]
    if not any(arg.endswith("trm.train.start") for arg in args):
        return None
    for flag, value in itertools.pairwise(args):
        if flag == "--checkpoint-path":
            return pathlib.Path(value).parent
    return None


def current_run() -> pathlib.Path | None:
    for pid in gpu_pids():
        run = run_dir_of(pid)
        if run is not None and (run / "metrics.csv").exists():
            return run
    return None


# ── whether it belongs on a television ───────────────────────────────────────


def constant(repo: pathlib.Path, module: str, name: str) -> int | float | None:
    """Read a constant out of the model's source without running any of it.

    Importing would pull in JAX, and nothing here may be able to touch the card.
    `ast` reads the assignment and executes nothing, the same way tools/mesh
    reads that repo's architecture.
    """
    try:
        tree = ast.parse((repo / module).read_text())
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            try:
                return ast.literal_eval(node.value)
            except (ValueError, TypeError):
                return None
    return None


def metadata(run: pathlib.Path) -> dict:
    try:
        return json.loads((run / "run_metadata.json").read_text())
    except (OSError, ValueError):
        return {}


def worth_watching(repo: pathlib.Path, run: pathlib.Path) -> tuple[bool, str]:
    """(verdict, reason). Being on the card is settled by how the run was found,
    so what is left is scale and duration."""
    params = metadata(run).get("parameters", {})
    budget = params.get("TRAIN_TOKEN_BUDGET") or constant(
        repo, "trm/config.py", "TRAIN_TOKEN_BUDGET"
    )
    if not isinstance(budget, (int, float)) or budget < MIN_BUDGET_TOKENS:
        return False, f"budget {budget} is under {MIN_BUDGET_TOKENS:,} tokens (~1h)"
    width = params.get("LATENT_DIM") or constant(repo, "trm/config.py", "LATENT_DIM")
    if not isinstance(width, (int, float)) or width < MIN_LATENT_DIM:
        return False, f"latent dim {width} is under the shipped {MIN_LATENT_DIM}"
    return True, f"{budget / 1e6:.0f}M tokens at dim {width}"


def tokens_per_step(repo: pathlib.Path, run: pathlib.Path) -> int:
    """Tokens one optimizer step consumes, from what the run recorded.

    The run's own parameters first, because the config file may have moved on
    since it launched. `TOKENS_PER_OPT_STEP` is written in the config as a
    product of these, which `constant` cannot evaluate, so it is multiplied out
    here the way the config does it: two prediction windows per micro-step.
    """
    params = metadata(run).get("parameters", {})
    parts = [
        params.get(name) or constant(repo, "trm/config.py", name)
        for name in ("ACCUMULATION_STEPS", "BATCH_SIZE", "MAX_SEQ_LEN")
    ]
    if all(isinstance(part, int) for part in parts):
        accumulation, batch, window = parts
        return accumulation * batch * 2 * window
    return 131_072


def last_step(metrics: pathlib.Path) -> int | None:
    """The step on the last row of a run's metrics, or None if it has none."""
    try:
        lines = metrics.read_text().splitlines()
        column = lines[0].split(",").index("step")
        for line in reversed(lines[1:]):
            cells = line.split(",")
            if len(cells) > column and cells[column].isdigit():
                return int(cells[column])
    except (OSError, ValueError, IndexError):
        pass
    return None


def progress(repo: pathlib.Path, run: pathlib.Path) -> tuple[int, int] | None:
    """(tokens trained on so far, the run's token budget), or None if unknown."""
    budget = metadata(run).get("parameters", {}).get("TRAIN_TOKEN_BUDGET") or constant(
        repo, "trm/config.py", "TRAIN_TOKEN_BUDGET"
    )
    step = last_step(run / "metrics.csv")
    if not isinstance(budget, (int, float)) or step is None:
        return None
    return step * tokens_per_step(repo, run), int(budget)


def redraw_every(repo: pathlib.Path, run: pathlib.Path) -> int:
    """Seconds between redraws: about twenty over the run's whole life.

    A six-hour ablation redraws every twenty minutes and a month-long base run
    every hour, which is what anybody actually wants to see — a picture that has
    visibly moved since the last glance, without a figure being rendered every
    minute for a curve that has not gone anywhere.
    """
    params = metadata(run).get("parameters", {})
    budget = params.get("TRAIN_TOKEN_BUDGET") or 0
    rows = 0
    first = last = None
    try:
        with (run / "metrics.csv").open() as handle:
            header = handle.readline().strip().split(",")
            step_at, clock_at = header.index("step"), header.index("wall_clock")
            for line in handle:
                cells = line.rstrip("\n").split(",")
                if len(cells) <= max(step_at, clock_at) or not cells[clock_at]:
                    continue
                stamp = datetime.datetime.fromisoformat(cells[clock_at].replace("Z", "+00:00"))
                first = first or (stamp, int(cells[step_at]))
                last, rows = (stamp, int(cells[step_at])), rows + 1
    except (OSError, ValueError, IndexError):
        rows = 0
    if rows < 2 or first is None or last is None or last[1] <= first[1] or not budget:
        return FASTEST
    seconds_per_step = (last[0] - first[0]).total_seconds() / (last[1] - first[1])
    whole_run = seconds_per_step * budget / tokens_per_step(repo, run)
    return int(min(SLOWEST, max(FASTEST, whole_run / REFRESHES_PER_RUN)))


# ── drawing and hanging ──────────────────────────────────────────────────────


def render(repo: pathlib.Path, run: pathlib.Path) -> bool:
    """Run that repo's own plotter. It pins itself to the CPU, so this cannot
    touch the card even by accident, and it is safe against a live run."""
    done = subprocess.run(
        [
            str(repo / "venv/bin/python"),
            "-m",
            "instruments.plots",
            "--log",
            str(run / "metrics.csv"),
            "--out",
            str(run),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=900,
        env={"PATH": "/usr/bin:/bin", "HOME": str(pathlib.Path.home()), "JAX_PLATFORMS": "cpu"},
    )
    if done.returncode:
        log(f"plotter failed: {done.stderr.strip()[-300:]}")
    return done.returncode == 0


# ── the loop ─────────────────────────────────────────────────────────────────


def watch(repo: pathlib.Path, cache: pathlib.Path, once: bool = False) -> int:
    showing: str | None = None
    drawn_at, cadence, last_busy = 0.0, FASTEST, time.time()

    while True:
        run = current_run()
        worth, why = worth_watching(repo, run) if run else (False, "card idle")

        if run and worth:
            last_busy = time.time()
            # Every pass rather than every redraw: a bar is one small write, and
            # it is the one thing here that should look live.
            done = progress(repo, run)
            if done:
                measure(*done)
            if run.name != showing or time.time() - drawn_at >= cadence:
                cadence = redraw_every(repo, run)
                log(f"{run.name}: {why} — drawing, next in {cadence // 60} min")
                if render(repo, run):
                    show(repo, run, cache)
                    showing, drawn_at = run.name, time.time()
        elif run:
            log(f"{run.name} is on the card but not worth watching: {why}")
        elif showing and time.time() - last_busy >= IDLE_SECONDS:
            log(f"card quiet for {IDLE_SECONDS // 60} minutes — packing up")
            clear()
            return 0

        if once:
            return 0
        time.sleep(POLL_SECONDS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=pathlib.Path, help="the TinyRefinementModel checkout")
    parser.add_argument(
        "--cache",
        type=pathlib.Path,
        default=pathlib.Path.home() / ".cache/starkhud/trm",
        help="where the letterboxed copies are kept",
    )
    parser.add_argument("--once", action="store_true", help="one pass, then exit")
    parser.add_argument("--clear", action="store_true", help="take the sheets down and exit")
    args = parser.parse_args()
    if args.clear:
        clear()
        return 0
    return watch(args.repo.expanduser().resolve(), args.cache.expanduser(), once=args.once)


if __name__ == "__main__":
    sys.exit(main())
