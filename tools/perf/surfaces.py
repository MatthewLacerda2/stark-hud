"""Is it still the same picture? The half of this rig worth keeping.

A timing says a change is cheaper. It does not say the change is *allowed*.
The board is the product here — `CLAUDE.md` says the look wins — so a
performance change is only safe to merge once somebody can show that what the
television draws did not move. Nobody can see eight extruded copies of a radar
shift by a pixel, and that is exactly the kind of thing a faster render path
does by accident.

So: hold the data still, wait for the page to stop mutating, and take the
rendered SVG of every mark on the board — the chart surfaces and the extrusion
copies behind them, which is everything a widget actually draws. Two arms are
compared element by element.

Text is not compared and neither are screenshots. Words are laid out by a font
stack, an image is rastered by whichever backend the instance has, and both
differ between a headless run and the television while the picture is the same
picture. The SVG is the geometry: every path, every position, every size,
stated rather than drawn.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from perf.cdp import Page

# Recharts numbers its generated clip paths from a counter that is global to the
# page, so `recharts7-clip` is a fact about mount order rather than about the
# drawing. A branch that mounts one more chart somewhere would shift every id
# below it and show as a difference in every surface on the board.
_GENERATED_ID = re.compile(r"recharts\d+")

MARKS = ".recharts-surface, [data-extrude-mark]"

SETTLE_JS = """
new Promise((done) => {
  let last = performance.now();
  const observer = new MutationObserver(() => { last = performance.now(); });
  observer.observe(document.body, {
    subtree: true, childList: true, attributes: true, characterData: true,
  });
  const check = () => {
    if (performance.now() - last > QUIET) { observer.disconnect(); done(true); return; }
    if (performance.now() - started > LIMIT) { observer.disconnect(); done(false); return; }
    setTimeout(check, 50);
  };
  const started = performance.now();
  check();
})
"""

DUMP_JS = """
Array.from(document.querySelectorAll(SELECTOR)).map((node) => {
  const box = node.getBoundingClientRect();
  return {
    at: [Math.round(box.x), Math.round(box.y), Math.round(box.width), Math.round(box.height)],
    svg: node.outerHTML,
  };
})
"""


@dataclass(frozen=True)
class Surface:
    """One drawn mark: where it is on the board, and the shape of it."""

    at: tuple[int, int, int, int]
    svg: str

    def key(self) -> str:
        x, y, w, h = self.at
        return f"{x},{y} {w}x{h}"


def settle(page: Page, quiet_ms: int = 600, limit_ms: int = 8000) -> bool:
    """Wait until nothing in the document has changed for `quiet_ms`.

    False means it never went quiet, and a comparison taken then would be
    comparing two animations caught at different moments. The caller should say
    so rather than report a difference.
    """
    js = SETTLE_JS.replace("QUIET", str(quiet_ms)).replace("LIMIT", str(limit_ms))
    return bool(page.evaluate(js))


def dump(page: Page) -> list[Surface]:
    """Every mark the board is drawing, in document order."""
    raw = page.evaluate(DUMP_JS.replace("SELECTOR", repr(MARKS))) or []
    return [Surface(at=(r["at"][0], r["at"][1], r["at"][2], r["at"][3]), svg=r["svg"]) for r in raw]


def _normalise(svg: str) -> str:
    return _GENERATED_ID.sub("recharts#", svg)


def compare(before: list[Surface], after: list[Surface]) -> list[str]:
    """What moved. An empty list is the whole point of this module."""
    if len(before) != len(after):
        return [f"the board drew {len(before)} marks before and {len(after)} after"]
    changed: list[str] = []
    for index, (a, b) in enumerate(zip(before, after, strict=True)):
        if a.at != b.at:
            changed.append(f"mark {index} moved: {a.key()} -> {b.key()}")
            continue
        # Normalised here rather than when the dump was taken, so that the
        # invariant sits next to the comparison it exists for and a saved dump
        # is still the markup the browser actually produced.
        left, right = _normalise(a.svg), _normalise(b.svg)
        if left == right:
            continue
        diff = difflib.unified_diff(
            _lines(left), _lines(right), fromfile="before", tofile="after", lineterm="", n=1
        )
        body = "\n".join(list(diff)[:20])
        changed.append(f"mark {index} at {a.key()} redrew:\n{body}")
    return changed


def _lines(svg: str) -> list[str]:
    """One tag per line, so a diff points at the element that changed."""
    return svg.replace("><", ">\n<").splitlines()
