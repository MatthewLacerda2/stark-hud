"""The interleaved sweep: two builds, two browsers, and samples taken in turn.

Why interleaved, and not one arm and then the other. This box is eight cores
and usually carries a training run as well as the board's own kiosk, and on
2026-09-20 the same `bun install` took 14.4 s under load and 0.75 s quiet — an
eighteenfold difference that had nothing to do with the thing being measured.
Run all of A and then all of B and any drift in the neighbours lands entirely
on one of them. Take them in turn, round after round, and it lands on both.

The other half of the defence is that an arm which is not being sampled is
*held*: its stand-in socket stops sending, its charts settle, and a settled
board costs about a tenth of a percent of a core. So the arms are not each
other's noise. Only one board is alive at a time, and which one takes it in
turn.

A round reports a range rather than a mean. Four rounds that disagree with each
other are four rounds worth seeing, and averaging them away is how a number
comes to look more certain than it is.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from perf import cost, report, surfaces
from perf.board import CADENCE_S, Board
from perf.cdp import Browser, Page
from perf.feed import Server

VIEWPORT = (1920, 1080)
WARMUP_TIMEOUT_S = 30.0

# Counts frames the way the board is actually driven, rather than asking the
# protocol for a rendering statistic: what matters is whether the page kept up.
COUNTER_JS = """
window.__perf = { frames: 0 };
const tick = () => { window.__perf.frames += 1; requestAnimationFrame(tick); };
requestAnimationFrame(tick);
true
"""


@dataclass
class Reading:
    arm: str
    round: int
    cpu: float
    processes: int
    fps: float
    load: float


@dataclass
class Arm:
    """One build, served and open in a browser of its own."""

    name: str
    commit: str
    server: Server
    browser: Browser
    page: Page
    readings: list[Reading] = field(default_factory=list)

    def hold(self) -> None:
        self.server.feed.hold()

    def resume(self) -> None:
        self.server.feed.resume()

    def close(self) -> None:
        self.page.close()
        self.browser.close()
        self.server.stop()


def open_arm(
    name: str, commit: str, dist: Path, port: int, profile: Path, *, headless: bool
) -> Arm:
    """Serve a build, open it, lay it out at the television's size, wait for widgets."""
    server = Server(dist, Board())
    server.start()
    browser = Browser.launch(server.url, port, profile, headless=headless)
    page = browser.page()
    page.viewport(*VIEWPORT)
    page.navigate(server.url)
    _wait_for_board(page)
    page.evaluate(COUNTER_JS)
    return Arm(name=name, commit=commit, server=server, browser=browser, page=page)


def _wait_for_board(page: Page) -> None:
    deadline = time.monotonic() + WARMUP_TIMEOUT_S
    while time.monotonic() < deadline:
        drawn = page.evaluate(f"document.querySelectorAll({surfaces.MARKS!r}).length")
        if isinstance(drawn, int) and drawn > 0:
            return
        time.sleep(0.5)
    raise RuntimeError("the board never drew a mark - is the bundle the one you think it is?")


def measure(arm: Arm, others: list[Arm], seconds: float, round_no: int) -> Reading:
    """One sample of one arm, with every other arm held still while it is taken."""
    for other in others:
        other.hold()
    arm.resume()
    # One cadence of running before the clock starts: the arm has just been let
    # go and its next reading may be anywhere in the next three seconds, so a
    # window opened now would catch part of a board that is not yet in rhythm.
    time.sleep(CADENCE_S)

    pids = [p.pid for p in arm.browser.processes()]
    frames_before = arm.page.evaluate("window.__perf.frames")
    cpu = cost.Cpu()
    cpu.start(pids)
    time.sleep(seconds)
    percent, counted = cpu.stop([p.pid for p in arm.browser.processes()])
    frames_after = arm.page.evaluate("window.__perf.frames")

    return Reading(
        arm=arm.name,
        round=round_no,
        cpu=percent,
        processes=counted,
        fps=(float(frames_after) - float(frames_before)) / seconds,
        load=cost.loadavg()[0],
    )


def run(arms: list[Arm], rounds: int, seconds: float) -> None:
    """Before, after, before, after. The order flips each round as well.

    Flipping is not superstition: within a round the first arm measured is the
    one that has just been let go, and the second has had a few more seconds of
    the other's browser sitting idle beside it. Over an even number of rounds
    each arm gets that position the same number of times.
    """
    for index in range(rounds):
        order = arms if index % 2 == 0 else list(reversed(arms))
        for arm in order:
            others = [a for a in arms if a is not arm]
            reading = measure(arm, others, seconds, index + 1)
            arm.readings.append(reading)
            print(
                f"  round {reading.round}  {reading.arm:<10} "
                f"{reading.cpu:6.1f} % of a core   {reading.fps:5.1f} fps   "
                f"load {reading.load:.2f}   ({reading.processes} processes)"
            )


# How many readings the board has taken when its picture is compared. Any fixed
# number does; it is fixed so that two runs compare the same drawing.
PICTURE_TICK = 3


def picture(arms: list[Arm]) -> list[str]:
    """Hold every arm still, give them all the same reading, and compare what they drew."""
    settled = Board()
    for _ in range(PICTURE_TICK):
        settled.advance()
    for arm in arms:
        arm.hold()
    # A tick already on its way out cannot be recalled, so the hold is given a
    # moment to take before the one reading everybody is judged on is sent.
    time.sleep(0.5)
    for arm in arms:
        arm.server.feed.push(settled.panels())
    quiet = True
    dumps: list[tuple[str, list[surfaces.Surface]]] = []
    for arm in arms:
        quiet = surfaces.settle(arm.page) and quiet
        dumps.append((arm.name, surfaces.dump(arm.page)))
    if not quiet:
        return ["the board never stopped moving, so the picture cannot be compared"]

    first_name, first = dumps[0]
    out = [f"{len(first)} marks drawn on {first_name}"]
    for name, other in dumps[1:]:
        changed = surfaces.compare(first, other)
        if not changed:
            out.append(f"{name} draws the same picture as {first_name}, mark for mark")
            continue
        out.append(f"{name} differs from {first_name} in {len(changed)} place(s):")
        out += [f"  {line}" for line in changed]
    return out


def summarise(arms: list[Arm], conditions: cost.Conditions) -> list[str]:
    """Everything this run found, with what it was taken under, then the baseline."""
    rows: list[tuple[str, str, str, str]] = [("arm", "cpu", "fps", "commit")]
    for arm in arms:
        cpus = [r.cpu for r in arm.readings]
        fps = [r.fps for r in arm.readings]
        rows.append(
            (
                arm.name,
                report.spread(cpus),
                f"{sum(fps) / len(fps):.1f}" if fps else "-",
                arm.commit,
            )
        )
    out = ["", "what it cost", "", *report.table(rows)]
    out += ["", "under these conditions", "", *conditions.lines()]
    if conditions.load_moved > 2:
        out.append(f"  warning      the load moved by {conditions.load_moved:.1f} during this run.")
        out.append("               Interleaving shares that between the arms; it does not")
        out.append("               make the absolute numbers comparable to another day's.")
    out += ["", *report.baseline_lines()]
    return out
