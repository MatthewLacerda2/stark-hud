#!/usr/bin/env python3
"""The training run that owns the GPU, as three charts.

    trm_run.py curve     <checkout>   train and held-out loss against tokens
    trm_run.py progress  <checkout>   how much of the token budget is done
    trm_run.py health    <checkout>   the gradient norm against its clip

One metric per call, the way `gpu.py util` and `gpu.py vram` are one gauge each:
a source writes one panel, so a widget is a call.

Nobody should have to remember to point the board at the run that is training,
so this watches the card instead. It asks the driver which processes hold memory
on the GPU, reads each one's `/proc/<pid>/cmdline` for `trm.train.start`, and
takes the run directory from its `--checkpoint-path`. Reading /proc rather than
guessing at the newest directory is what keeps it right on a box where several
runs exist. For an hour after the card goes quiet the run that was on it keeps
the widgets — the end of a curve is the part worth looking at — and then they
come down on their own, which is what printing no rows does to a `transient`
source: the panel comes off the board rather than sitting there saying "no data".

A run has to earn the television, and the rule is about scale and duration,
never what a run is called: at least 20M tokens of budget — about an hour at this
box's measured ~5.7k tok/s — at the shipped width of 960. A smoke test and a toy
ablation are work in progress, and nobody watches those from a sofa.

The numbers come out of the run's own `metrics.csv` with the `csv` module, and
what they are read against — the size of an optimiser step, the gradient clip —
out of that repository's source with `ast`. Never imported: importing
`trm.config` pulls JAX in and could touch the card, which is the one thing a
board is not allowed to do. Standard library only, like every collector here.
"""

import argparse
import ast
import csv
import fcntl
import itertools
import json
import subprocess
import time
from pathlib import Path
from typing import Any

# What a run has to be before it is worth a television. Both are about scale and
# duration; neither looks at what the run is called.
MIN_BUDGET_TOKENS = 20_000_000  # ~1 hour at this box's measured ~5.7k tok/s
MIN_LATENT_DIM = 960  # the shipped width; a toy ablation is narrower

IDLE = 60 * 60.0  # how long a finished run keeps the board

# How many points go up the wire. A month-long run has hundreds of thousands of
# rows and a widget nine cells wide can draw about sixty of them; the bars get a
# quarter of that because they are four cells wide and a bar needs room to be a
# bar. Evenly spaced across the whole run rather than the last N, so what is on
# the wall is the run and not its last few minutes.
POINTS = {"curve": 60, "health": 24}

# Where the numbers this reads a run against live, over in the model's
# repository: the width and the budget, the size of an optimiser step, and the
# gradient clip.
SOURCES = ("trm/config.py", "trm/train/optimizers.py")


# ------------------------------------------------------- finding the run
def gpu_pids() -> list[int]:
    """Every process holding memory on the card, as far as we can tell.

    Nothing when the driver cannot be asked, which is not a lie the board pays
    for: a run that is training is writing rows, and `lately` below keeps it on
    the wall on that evidence alone.

    It takes gpu.py's lock for gpu.py's reason — a wedged driver puts nvidia-smi
    into uninterruptible sleep, where a timeout fires and kills nothing. The
    import is inside the function because a collector is run as a script, and
    being run that way is what makes the one next door importable.
    """
    from gpu import LOCK

    with open(LOCK, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return []  # the gauges are asking right now; a minute will do
        try:
            listing = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return []
    return [int(word) for word in listing.split() if word.isdigit()]


def run_of(pid: int) -> Path | None:
    """The run directory a trainer is writing into, out of its command line.

    The trainer is launched as `-m trm.train.start --checkpoint-path
    <run>/checkpoints`, so the run is that path's parent. Anything else on the
    card carries no such flag and is not a run.
    """
    try:
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except OSError:
        return None
    args = [part.decode(errors="replace") for part in argv if part]
    if not any(arg.endswith("trm.train.start") for arg in args):
        return None
    for flag, value in itertools.pairwise(args):
        if flag == "--checkpoint-path":
            return Path(value).parent
    return None


def lately(repo: Path) -> Path | None:
    """The run that wrote a metric row most recently, if it was within the hour.

    What holds the widgets for the hour after the card empties, and it is the
    whole of this collector's memory: a run stops appending to its metrics.csv
    the moment it stops, so the file says when the card went quiet and nothing
    here has to remember anything between one minute and the next.

    Mtimes only decide what to keep showing. Which run *owns the card* is
    answered by /proc, above, and always was — that is the answer that goes
    wrong when several run directories exist.
    """
    logs = sorted(repo.glob("runs/*/metrics.csv"), key=lambda log: log.stat().st_mtime)
    if logs and time.time() - logs[-1].stat().st_mtime < IDLE:
        return logs[-1].parent
    return None


def subject(repo: Path) -> Path | None:
    """The run the board should be showing, if there is one."""
    on_the_card = (run_of(pid) for pid in gpu_pids())
    return next((run for run in on_the_card if run), None) or lately(repo)


# ------------------------------------------- what the run says it is
def constants(source: str) -> dict[str, float]:
    """The plainly-assigned numbers of a Python file, without running it.

    Anything computed is left out — most of `trm/config.py` is — and that is the
    point: this reads a file, it does not evaluate one.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    found: dict[str, float] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError):
            continue
        if isinstance(value, int | float) and not isinstance(value, bool):
            found.update({t.id: value for t in node.targets if isinstance(t, ast.Name)})
    return found


def recipe(repo: Path, run: Path) -> dict[str, Any]:
    """What this run was made of: the repository's constants, then its own.

    A run is a recipe and the recipe has been re-tuned since, so what the run
    wrote down wins over what the files say now. The files are there for what a
    run does not record — the gradient clip — and for one that recorded nothing.
    """
    numbers: dict[str, Any] = {}
    for name in SOURCES:
        try:
            numbers.update(constants((repo / name).read_text()))
        except OSError:
            continue
    try:
        params = json.loads((run / "run_metadata.json").read_text()).get("parameters", {})
    except (OSError, ValueError):
        params = {}
    numbers.update({key: value for key, value in params.items() if value is not None})
    return numbers


def number(made_of: dict[str, Any], name: str) -> float:
    """One constant as a number, or zero when it is missing or unreadable."""
    try:
        return float(made_of.get(name) or 0)
    except (TypeError, ValueError):
        return 0.0


def worth_watching(made_of: dict[str, Any]) -> bool:
    """Whether this run has earned the television.

    Being on the card is settled by how the run was found, so what is left is
    scale and duration. A run that recorded no budget is refused rather than
    guessed at: without one there is no telling an hour of training from a minute
    of it, and the gauge has nothing to be a proportion of.
    """
    budget, width = number(made_of, "TRAIN_TOKEN_BUDGET"), number(made_of, "LATENT_DIM")
    return budget >= MIN_BUDGET_TOKENS and width >= MIN_LATENT_DIM


def tokens_per_opt_step(made_of: dict[str, Any]) -> float:
    """What one optimiser step is worth in tokens, by the run's own recipe.

    `ACCUMULATION_STEPS * BATCH_SIZE * 2 * MAX_SEQ_LEN` is the model repository's
    own formula, and 131,072 on this box today. Derived rather than written down,
    because those constants move and an old run's steps are worth what they were
    worth when it ran.
    """
    sizes = [number(made_of, name) for name in ("ACCUMULATION_STEPS", "BATCH_SIZE", "MAX_SEQ_LEN")]
    return 2 * sizes[0] * sizes[1] * sizes[2]


# ---------------------------------------------------- reading the log
def log_of(run: Path) -> str:
    """A run's metrics.csv, or nothing when it has not written one yet."""
    try:
        return (run / "metrics.csv").read_text()
    except OSError:
        return ""


def measurements(log: str) -> list[dict[str, str]]:
    """The rows of a metrics.csv that are whole enough to plot.

    This is read while the trainer is appending to it, so the last line is
    sometimes half of one: fewer columns than the header, and a number that has
    only had half of itself written. A short row is dropped rather than drawn,
    because half of 11.2801 is 11.28 and that is a plausible-looking lie.
    """
    return [
        row
        for row in csv.DictReader(log.splitlines())
        if (row.get("step") or "").isdigit() and None not in row.values()
    ]


def sample(rows: list[dict[str, str]], most: int) -> list[dict[str, str]]:
    """At most `most` rows, evenly spaced, keeping the first and the last.

    The last of a run is not the shape of it: a curve is about where it started
    and where it is going, so what comes off is the middle, thinned.
    """
    if len(rows) <= most:
        return rows
    step = (len(rows) - 1) / (most - 1)
    return [rows[round(at * step)] for at in range(most)]


def reading(row: dict[str, str], column: str) -> float | None:
    """One cell as a number, or None when the run did not write it.

    `val_ce` is only on the rows a held-out probe ran, and an old run has no
    `applied_grad_norm` at all. A gap has to stay a gap: drawn as a zero it is a
    model that briefly became perfect.
    """
    try:
        return float(row[column])
    except (KeyError, TypeError, ValueError):
        return None


# ------------------------------------------------- what each widget gets
def curve(rows: list[dict[str, str]], made_of: dict[str, Any]) -> list[dict]:
    """Train and held-out cross-entropy against tokens, in millions.

    The held-out line is the only thing on this board that says how good the
    model is. It is measured every few hundred steps rather than every step, so
    it is carried forward to the rows in between: a measurement holds until it is
    taken again, and a line broken into sixty separate points draws as nothing at
    all with the dots turned off. Before the first probe there is no value to
    carry and the key is left out, so that line starts where the measuring did.
    """
    per_step = tokens_per_opt_step(made_of)
    drawn, held = [], None
    for row in sample(rows, POINTS["curve"]):
        probe = reading(row, "val_ce")
        held = probe if probe is not None else held
        point: dict[str, float] = {"tokens": round(int(row["step"]) * per_step / 1e6, 1)}
        if (train := reading(row, "ce")) is not None:
            point["train"] = round(train, 3)
        if held is not None:
            point["held"] = round(held, 3)
        drawn.append(point)
    return drawn


def progress(rows: list[dict[str, str]], made_of: dict[str, Any]) -> list[dict]:
    """How far through its token budget the run is, as one ring.

    The ring carries the proportion, so the reading under it spells out the part
    the ring cannot: how many tokens that is.
    """
    budget = number(made_of, "TRAIN_TOKEN_BUDGET")
    tokens = int(rows[-1]["step"]) * tokens_per_opt_step(made_of)
    return [
        {
            "label": f"{tokens / 1e6:.1f}/{budget / 1e6:.1f}M",
            "pct": round(min(100.0, 100 * tokens / budget), 1),
        }
    ]


def health(rows: list[dict[str, str]], made_of: dict[str, Any]) -> list[dict]:
    """The gradient norm, in multiples of the clip it is held to.

    Divided by `CLIP_NORM` rather than drawn against it, because a threshold is
    part of the panel and the panel is a line in a config file — this way the
    line the board draws at 1 is the clip, whatever the clip is that week. Above
    1 the clip is what set the step size, not the schedule, and the bar turns.

    `applied_grad_norm` is what the optimiser actually stepped with;
    `grad_norm_avg` is the older runs' only answer and is read when the newer
    column is not there.
    """
    clip = number(made_of, "CLIP_NORM") or 1.0
    drawn = []
    for row in sample(rows, POINTS["health"]):
        norm = reading(row, "applied_grad_norm")
        norm = reading(row, "grad_norm_avg") if norm is None else norm
        if norm is not None:
            drawn.append({"step": row["step"], "norm": round(norm / clip, 3)})
    return drawn


WIDGETS = {"curve": curve, "progress": progress, "health": health}


def main() -> None:
    """Print one widget's rows, or nothing at all when no run deserves one."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("widget", choices=sorted(WIDGETS))
    parser.add_argument("repo", type=Path, help="a TinyRefinementModel checkout")
    args = parser.parse_args()

    run = subject(args.repo)
    made_of = recipe(args.repo, run) if run else {}
    rows = measurements(log_of(run)) if run else []
    if not rows or not worth_watching(made_of):
        print("[]")
        return
    print(json.dumps(WIDGETS[args.widget](rows, made_of)))


if __name__ == "__main__":
    main()
