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
    """One figure worth remembering, with what it was a figure of.

    `other` is the GPU column where a GPU figure means anything, and the frame
    rate where it does not — which is every headless row, and every row taken
    on a day the card was busy with something else.
    """

    what: str
    cpu: str
    other: str


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

# What this rig read on the day it was written, on its own fixture board, so
# that a run next year has something it is actually comparable to. The two
# blocks above were taken on other boards and are shape, not scale.
#
# Headless, two arms interleaved, four rounds of 20 s, load around 6 on 8 cores.
FIXTURE = [
    Landmark("the fixture board, before #133 (868314c)", "168 - 181 %", "31 fps"),
    Landmark("the fixture board, master of 2026-09-20", "140 - 153 %", "51 fps"),
    Landmark("...and with the pie and bar animations off", "55 - 60 %", "56 fps"),
]

# The television, re-measured 2026-09-20 after that day's deploy, 12 s samples.
# Lower than 2026-09-19 throughout, because #133 had landed and the board had
# changed; the shape is the same and the split still adds up.
TELEVISION_TODAY = [
    Landmark("the board as it is", "104 %", "unreadable"),
    Landmark("background video paused, widgets drawn", "54 %", "unreadable"),
    Landmark("widgets hidden, video playing", "56 %", "unreadable"),
    Landmark("both stopped - the floor", "1.5 %", "unreadable"),
]

NOTES = [
    "The background video is about 70 % of a core on its own, decoded in",
    "software: this machine has no libva-nvidia-driver, so 1080p30 costs a core's",
    "worth of CPU for a blurred loop. It is not in the headless arms at all.",
    "The floor - nothing drawn, video paused - is 3.3 % of a core and no GPU.",
    "An earlier run put that floor at 67 %. It was wrong: the video had been",
    "hidden with display:none, and a hidden video goes on decoding.",
    "",
    "On 2026-09-20 no GPU figure could be taken at all: a training run held the",
    "card at 77 % through every state, including the one with nothing drawn. A",
    "gpu column that reads the same in all four rows is the card's, not the",
    "board's, and the rig prints who else is on it so you can see that coming.",
    "",
    "The pie and the bar still take recharts' 1500 ms default animation - the",
    "gauge and the radar were given `SWEEP_MS` in #133 and these two were not.",
    "On the fixture board that is about ninety points of a core, and the settled",
    "picture is identical mark for mark. Measured, not guessed; see #142/#143.",
]


def baseline_lines() -> list[str]:
    """The baseline, printed against every run so a number lands somewhere."""
    out = ["baseline, 2026-09-19", "", "  on the television (board of that day, video on):"]
    out += [f"    {m.what:<42} {m.cpu:>9} cpu  {m.other:>9} gpu" for m in TELEVISION]
    after = TELEVISION_AFTER
    out.append(f"    {after.what:<42} {after.cpu:>9} cpu  {after.other:>9} gpu")
    out += ["", "  and again on 2026-09-20, after that day's deploy:"]
    out += [f"    {m.what:<42} {m.cpu:>9} cpu  {m.other:>11} gpu" for m in TELEVISION_TODAY]
    out += ["", "  headless, four charts at the real cadence:"]
    out += [f"    {m.what:<42} {m.cpu:>9} cpu  {m.other:>9} gpu" for m in HEADLESS]
    out += ["", "  this rig's own fixture board, 2026-09-20 - the comparable one:"]
    out += [f"    {m.what:<42} {m.cpu:>11} cpu  {m.other:>7}" for m in FIXTURE]
    out += ["", *(f"  {n}" if n else "" for n in NOTES)]
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
