/**
 * Whether an arrow's word is drawn at all, and the two different ways it can
 * fail to be: an arrow too short to carry it, and an arrow whose midpoint
 * leaves no room on the widget for the word to sit.
 *
 * The widget's shape is stated rather than measured, like the rest of a flow's
 * arithmetic, so every one of these is a fact about the payload and the shape
 * and not about a browser that is not running.
 */
import { describe, expect, it } from "vitest";
import {
  crowded,
  flow,
  link,
  LOOP,
  only,
  PIPELINE,
  REFINE_LOOP,
  REFINER,
  RETRY,
  SQUARE,
  TALL,
  WIDE,
} from "@/lib/flow.fixtures";
import type { FlowPayload } from "@/lib/schemas/board";
import { arrows, cells, inside, layout, midpoint, roomy } from "@/lib/flow";

/** The word each arrow in this flow carries, once the drawing has had its say. */
function words(payload: FlowPayload, size: typeof LOOP) {
  const laid = layout(payload, size.cols, size.rows);
  return arrows(payload, laid).map(({ link: carried }) => carried.label);
}

describe("whether an arrow is long enough for a word", () => {
  it("drops a word the arrow is too short to hold", () => {
    expect(roomy("ok", 3)).toBe(true);
    expect(roomy("ok", 0.5)).toBe(false);
  });

  it("drops a long word off an arrow a short one would have fitted", () => {
    // gantt's `roomy` can ignore the length because a bar clips its own name.
    // An arrow clips nothing, so a long word would overhang both ends.
    expect(roomy("ok", 2)).toBe(true);
    expect(roomy("needs another build", 2)).toBe(false);
  });
});

describe("whether a word lands on the widget", () => {
  it("takes the word's own box, not the point it hangs from", () => {
    // One anchor, a tenth of the widget clear of the right edge. A short word
    // around it is on the glass and a long one is not, and nothing about the
    // point itself says which.
    const at = { x: 0.9, y: 0.5 };

    expect(inside("ok", at, 12, 4)).toBe(true);
    expect(inside("all the way round again", at, 12, 4)).toBe(false);
  });

  it("watches all four edges, not the one the bug was seen at", () => {
    // Half a cell of word either side of the anchor in a 12x4 widget is a
    // twenty-fourth of the width; a line of it is about a twenty-seventh of the
    // height. Two hundredths in from any edge is inside both.
    const near = 0.02;
    const far = 0.5;

    expect(inside("abc", { x: near, y: far }, 12, 4)).toBe(false);
    expect(inside("abc", { x: 1 - near, y: far }, 12, 4)).toBe(false);
    expect(inside("abc", { x: far, y: near }, 12, 4)).toBe(false);
    expect(inside("abc", { x: far, y: 1 - near }, 12, 4)).toBe(false);
    expect(inside("abc", { x: far, y: far }, 12, 4)).toBe(true);
  });

  it("reads one word two ways in widgets of two shapes", () => {
    // A cell across a narrow widget is a larger share of it than a cell across
    // a broad one, which is the whole reason the estimate is in cells.
    const at = { x: 0.88, y: 0.5 };

    expect(inside("build", at, 12, 4)).toBe(true);
    expect(inside("build", at, 3, 9)).toBe(false);
  });
});

describe("the loop that #94 was written about", () => {
  it("keeps its word, which is not what the report said", () => {
    // Off the television: a 5.98x9.6 widget, a chain of five, and a way back
    // from `gate` to `refine` carrying `x6`. The report reads the clipping onto
    // this payload; this payload does not clip. Two characters at a fifth of a
    // cell, bowed out of boxes whose right face is at 0.73 of the width, land
    // between 0.859 and 0.925 of it. Pinned so that the next reading of this
    // bug starts from the measurement and not from the account.
    expect(words(flow(REFINER, REFINE_LOOP), LOOP)).toEqual([
      null,
      null,
      null,
      "×6",
      null,
    ]);
  });

  it("drops it once the diagram is wide enough to crowd the bow", () => {
    // What does clip it in that same widget: ranks four boxes wide. The
    // outermost box reaches 0.9325 of the width, so the bow has a sixteenth of
    // the widget left to work in and the word ends past 1.
    expect(words(crowded(3, "×6"), LOOP).at(-1)).toBe("×6");
    expect(words(crowded(4, "×6"), LOOP).at(-1)).toBeNull();
  });

  it("drops it off the bottom of a wide widget too", () => {
    // A flow running rightwards loops beneath itself, so the near edge is the
    // bottom one, and it goes sooner there: a line of text is a larger share of
    // four rows than of nine and a half.
    expect(words(crowded(2, "×6"), WIDE).at(-1)).toBe("×6");
    expect(words(crowded(3, "×6"), WIDE).at(-1)).toBeNull();
  });

  it("drops a long word off a long way back, which `roomy` lets through", () => {
    // The case the length test was never going to catch: the run is 7.68 cells,
    // so there is length to spare, and the word still ends a twentieth of the
    // widget past its right edge. How long the arrow is and where it is are two
    // questions, and #94 is the second one.
    const payload = flow(PIPELINE, [
      ...RETRY.slice(0, 3),
      link("ship", "clone", { label: "start over" }),
    ]);
    const laid = layout(payload, LOOP.cols, LOOP.rows);
    const back = only(arrows(payload, laid), "ship", "clone");
    const run = cells(back.start, back.end, LOOP.cols, LOOP.rows);

    expect(roomy("start over", run)).toBe(true);
    expect(inside("start over", midpoint(back), LOOP.cols, LOOP.rows)).toBe(
      false,
    );
    expect(words(payload, LOOP).at(-1)).toBeNull();
  });

  it("leaves an ordinary word alone, in every widget shape", () => {
    for (const size of [WIDE, TALL, SQUARE, LOOP])
      expect(words(flow(PIPELINE, RETRY), size).at(-1)).toBe("red");
  });
});
