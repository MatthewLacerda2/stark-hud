"""The 2026-09-19 baseline, and how a run says what it found.

These numbers are kept here so that the next person to ask "what does the board
cost" is answered by a program rather than by a search through closed issues.
They are landmarks, not thresholds: nothing fails a gate for missing them, and
this whole directory is deliberately outside `make check`.

Read them with their conditions attached. The television numbers were taken on
the real board of that day — seventeen widgets, a background video, a paused
YouTube widget — on a card shared with a training run. The headless numbers
were taken on four charts fed by a stand-in socket. **Neither was taken on this
rig's fixture board**, which is a fixed nine widgets chosen to cover every chart
kind. So a figure from `make perf` is comparable to another figure from
`make perf`, and comparable to what is below only in shape: the same fix should
still be worth roughly the same proportion.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Landmark:
    what: str
    cpu: str
    gpu: str


# On the television, over the kiosk on port 9222, 12 s samples. GPU from
# `nvidia-smi`, CPU from `/proc/<pid>/stat` deltas over the renderer and the GPU
# process. This is the split that found the board is two things, not one.
TELEVISION = [
    Landmark("the board as it is", "197 %", "27.7 %"),
    Landmark("background video paused, widgets drawn", "135 %", "23.0 %"),
    Landmark("widgets hidden, video playing", "69 %", "0 %"),
    Landmark("both stopped - the real floor", "3.3 %", "0 %"),
]

# After #133 shortened two recharts animations nobody had chosen, the same
# board on the same television.
TELEVISION_AFTER = Landmark("the board after #133", "133 %", "20 %")

# Headless, in a browser of the rig's own, four charts at the real 3 s cadence,
# three bundles interleaved over four rounds of 20 s. No GPU figure: software
# raster. This is the arithmetic `make perf` reproduces.
HEADLESS = [
    Landmark("every widget together, before #133", "68 %", "not reported"),
    Landmark("every widget together, after #133", "21 %", "not reported"),
    Landmark("with no movement at all", "8 - 11 %", "not reported"),
]

NOTES = [
    "The background video is about 70 % of a core on its own, decoded in",
    "software: this machine has no libva-nvidia-driver, so 1080p30 costs a core's",
    "worth of CPU for a blurred loop. It is not in the headless arms at all.",
    "The floor - nothing drawn, video paused - is 3.3 % of a core and no GPU.",
    "An earlier run put that floor at 67 %. It was wrong: the video had been",
    "hidden with display:none, and a hidden video goes on decoding.",
]


def baseline_lines() -> list[str]:
    """The baseline, printed against every run so a number lands somewhere."""
    out = ["baseline, 2026-09-19", "", "  on the television (board of that day, video on):"]
    out += [f"    {m.what:<42} {m.cpu:>9} cpu  {m.gpu:>9} gpu" for m in TELEVISION]
    after = TELEVISION_AFTER
    out.append(f"    {after.what:<42} {after.cpu:>9} cpu  {after.gpu:>9} gpu")
    out += ["", "  headless, four charts at the real cadence:"]
    out += [f"    {m.what:<42} {m.cpu:>9} cpu  {m.gpu:>9} gpu" for m in HEADLESS]
    out += [""] + [f"  {n}" for n in NOTES]
    return out


def table(rows: list[tuple[str, str, str, str]]) -> list[str]:
    """A fixed-width table. Four columns, because every run here has four things to say."""
    widths = [max(len(r[c]) for r in rows) for c in range(4)]
    return [
        "  "
        + "  ".join(
            cell.ljust(widths[c]) if c == 0 else cell.rjust(widths[c]) for c, cell in enumerate(row)
        )
        for row in rows
    ]


def spread(values: list[float]) -> str:
    """A range, not a mean: four rounds that disagree are four rounds worth seeing."""
    if not values:
        return "-"
    if len(values) == 1:
        return f"{values[0]:.1f} %"
    return f"{min(values):.1f} - {max(values):.1f} %"
