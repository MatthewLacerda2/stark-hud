"""Pricing the television itself: the only place a GPU figure means anything.

The kiosk opens a debugging port, and this attaches to it. It does not navigate
it, reload it, or touch `state/board.hud`. What it changes is one injected
stylesheet and, for one of the four states, the play/pause of one video element
— and it puts both back in a `finally`, because the television is somebody's
living room and a rig that leaves it hidden is worse than no rig.

The split is the one from 2026-09-19, and it is a split for a reason: the board
turned out to be two programs sharing a screen. A blurred loop decoded in
software is most of the CPU, and the widgets are most of the card. One number
for "the board" hides that, and hid it for a day.

**A hidden video goes on decoding.** `display:none` removes a video from the
picture and not from the decoder, and a run that hid one and called the result
a floor reported 67 % of a core as unexplained, which then went into an issue as
a mystery to be solved. There was no mystery. So the hiding and the pausing are
two separate switches here, and they are never confused again.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from perf import cost, report
from perf.cdp import Browser, Page

# One stylesheet, one id, removed by id. Nothing else about the page is written.
STYLE_ID = "stark-perf-rig"

HIDE_WIDGETS = ".depth-stage { display: none !important; }"

# The background is a <video> the board serves from its media endpoint. Named by
# its source rather than by being the only video on the page, because a media
# widget is a video too and pausing the film somebody is watching is not a
# measurement anybody asked for.
VIDEO_JS = "document.querySelector('video[src*=\"/media/background\"]')"


@dataclass(frozen=True)
class State:
    """One of the four things the board can be, and how to put it in that state."""

    what: str
    widgets: bool
    video: bool


STATES = [
    State("the board as it is", widgets=True, video=True),
    State("background video paused, widgets drawn", widgets=True, video=False),
    State("widgets hidden, video playing", widgets=False, video=True),
    State("both stopped - the floor", widgets=False, video=False),
]


def _apply(page: Page, state: State) -> None:
    css = "" if state.widgets else HIDE_WIDGETS
    page.evaluate(
        f"""
        (() => {{
          let tag = document.getElementById({STYLE_ID!r});
          if (!tag) {{
            tag = document.createElement('style');
            tag.id = {STYLE_ID!r};
            document.head.appendChild(tag);
          }}
          tag.textContent = {css!r};
          const video = {VIDEO_JS};
          if (video) {{ {"video.play().catch(() => {});" if state.video else "video.pause();"} }}
          return true;
        }})()
        """
    )


def _restore(page: Page) -> None:
    page.evaluate(
        f"""
        (() => {{
          const tag = document.getElementById({STYLE_ID!r});
          if (tag) tag.remove();
          const video = {VIDEO_JS};
          if (video && video.paused) video.play().catch(() => {{}});
          return true;
        }})()
        """
    )


def run(port: int, seconds: float, page_id: str | None = None) -> list[str]:
    """Walk the four states, measure each, put the board back, and report.

    The order matters less than it looks: every state is entered from scratch
    and given a settling pause, and nothing here accumulates. What does matter
    is that the board is left in the first state, which is the one it was in.
    """
    browser = Browser.attach(port)
    page = browser.page(page_id)
    tenants = cost.gpu_tenants()
    conditions = cost.Conditions(
        where="the television (live kiosk, attached read-only)",
        browser=browser.cdp.send("Browser.getVersion").get("product", "unknown"),
        cores=os.cpu_count() or 0,
        load_start=cost.loadavg(),
        gpu_tenants=tenants,
    )
    rows: list[tuple[str, str, str, str]] = [("state", "cpu", "gpu", "watts")]
    try:
        for state in STATES:
            _apply(page, state)
            # Long enough for the compositor to notice, and for a paused decoder
            # to actually stop: neither is instant and both are what is measured.
            time.sleep(2.0)
            rows.append(_sample(browser, state, seconds))
    finally:
        _restore(page)
        page.close()
        browser.close()

    conditions.load_end = cost.loadavg()
    out = ["", "what the television costs", "", *report.table(rows)]
    out += ["", "under these conditions", "", *conditions.lines()]
    if tenants:
        out.append("  gpu note     the card is shared, so a gpu figure is a difference between")
        out.append("               these rows, not a number belonging to the board alone.")
    out += ["", *report.baseline_lines()]
    return out


def _sample(browser: Browser, state: State, seconds: float) -> tuple[str, str, str, str]:
    pids = [p.pid for p in browser.processes()]
    gpu = cost.Gpu()
    cpu = cost.Cpu()
    gpu.start()
    cpu.start(pids)
    time.sleep(seconds)
    percent, _ = cpu.stop([p.pid for p in browser.processes()])
    card = gpu.stop()
    return (
        state.what,
        f"{percent:.1f} %",
        f"{card[0]:.1f} %" if card else "-",
        f"{card[1]:.1f} W" if card else "-",
    )
