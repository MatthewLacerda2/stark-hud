/**
 * What a gesture means, without a browser.
 *
 * The board is a space rather than a set of slots, so this is where "the user
 * dragged the widget over there" turns into four numbers. Overlap is not asked
 * about here on purpose: the server owns that, and a refusal is what sends the
 * widget home.
 */
import { describe, expect, it } from "vitest";
import { dragged, landed, same, MIN_SIZE, type Rect } from "@/lib/drag";

const BOARD = { cols: 32, rows: 18 };
const WIDGET: Rect = { x: 4, y: 2, w: 8, h: 4 };

describe("moving a widget", () => {
  it("puts it exactly where the pointer went, with snapping off", () => {
    expect(dragged(WIDGET, "move", { x: 1.4, y: -0.7 }, BOARD, false)).toEqual({
      x: 5.4,
      y: 1.3,
      w: 8,
      h: 4,
    });
  });

  it("is pulled onto a cell when it comes near one", () => {
    expect(dragged(WIDGET, "move", { x: 1.1, y: -0.9 }, BOARD, true)).toEqual({
      x: 5,
      y: 1,
      w: 8,
      h: 4,
    });
  });

  it("keeps its decimals when it stops between cells", () => {
    // The magnet is the point. Rounding every position to the nearest cell is
    // not soft snapping, it is the grid back again — it makes the fractional
    // coordinates unreachable by hand, which is what they were for.
    expect(dragged(WIDGET, "move", { x: 1.4, y: -0.7 }, BOARD, true)).toEqual({
      x: 5.4,
      y: 1.3,
      w: 8,
      h: 4,
    });
  });

  it("is not pulled at all while the modifier is held", () => {
    expect(dragged(WIDGET, "move", { x: 1.1, y: -0.9 }, BOARD, false)).toEqual({
      x: 5.1,
      y: 1.1,
      w: 8,
      h: 4,
    });
  });

  it("stops at the walls rather than leaving the board", () => {
    const off = dragged(WIDGET, "move", { x: -99, y: 99 }, BOARD, false);
    expect(off).toEqual({ x: 0, y: BOARD.rows - 4, w: 8, h: 4 });
  });
});

describe("resizing a widget", () => {
  it("moves the near edge and leaves the far one alone", () => {
    expect(dragged(WIDGET, "w", { x: -2, y: 0 }, BOARD, false)).toEqual({
      x: 2,
      y: 2,
      w: 10,
      h: 4,
    });
    expect(dragged(WIDGET, "e", { x: 2, y: 0 }, BOARD, false)).toEqual({
      x: 4,
      y: 2,
      w: 10,
      h: 4,
    });
  });

  it("takes both axes from a corner", () => {
    expect(dragged(WIDGET, "se", { x: 1.5, y: 1.5 }, BOARD, false)).toEqual({
      x: 4,
      y: 2,
      w: 9.5,
      h: 5.5,
    });
  });

  it("shuts to the smallest a widget may be, never inside out", () => {
    const shut = dragged(WIDGET, "e", { x: -99, y: 0 }, BOARD, false);
    expect(shut).toEqual({ x: 4, y: 2, w: MIN_SIZE, h: 4 });
  });

  it("stops growing at the wall", () => {
    expect(dragged(WIDGET, "e", { x: 99, y: 0 }, BOARD, false).w).toBe(
      BOARD.cols - WIDGET.x,
    );
  });
});

describe("a gesture that asked for nothing", () => {
  it("is recognised, so a click is not sent to the server as a move", () => {
    expect(
      same(WIDGET, dragged(WIDGET, "move", { x: 0.2, y: 0 }, BOARD, true)),
    ).toBe(true);
    expect(
      same(WIDGET, dragged(WIDGET, "move", { x: 0.2, y: 0 }, BOARD, false)),
    ).toBe(false);
  });
});

/**
 * Where a drop comes to rest among the widgets already there.
 *
 * Three outcomes and no others: the widget stays where it was put, it backs out
 * of what it clipped, or it goes home. Every number below is worked out by
 * hand, so a test that changes is a decision that changed — see issue #154 for
 * the four the user made.
 */
describe("dropping a widget among its neighbours", () => {
  /** Nothing else on the board. The gap is the whole board. */
  it("leaves a drop alone when there is nothing in the way", () => {
    expect(landed(WIDGET, [], BOARD, true)).toEqual(WIDGET);
  });

  it("goes flush against a neighbour's edge it came near", () => {
    // The widget's right edge is at 12 and the neighbour's left edge at 12.1:
    // a tenth of a cell apart, well inside the magnet, and a tenth of a cell is
    // a gap nobody meant to leave.
    const neighbour = { x: 12.1, y: 2, w: 6, h: 4 };
    expect(landed(WIDGET, [neighbour], BOARD, true)?.x).toBeCloseTo(4.1);
  });

  it("is left where the pointer put it while the modifier is held", () => {
    const neighbour = { x: 12.1, y: 2, w: 6, h: 4 };
    expect(landed(WIDGET, [neighbour], BOARD, false)).toEqual(WIDGET);
  });
});

describe("a drop that clipped somebody", () => {
  it("slides off and comes to rest against their edge", () => {
    // An eighth of itself over the neighbour: it backs out by one column and
    // stops where the two edges meet. It does not move anywhere else.
    const neighbour = { x: 11, y: 2, w: 6, h: 4 };
    expect(landed(WIDGET, [neighbour], BOARD, true)).toEqual({
      x: 3,
      y: 2,
      w: 8,
      h: 4,
    });
  });

  it("backs out whichever way it is least far in", () => {
    // Mostly past this one, so the way out is forwards rather than back.
    const neighbour = { x: 0, y: 2, w: 5, h: 4 };
    expect(landed(WIDGET, [neighbour], BOARD, true)).toEqual({
      x: 5,
      y: 2,
      w: 8,
      h: 4,
    });
  });

  it("slides at exactly a fifth swallowed, and goes home just past it", () => {
    // Ten columns wide, so a two-column bite is a fifth of its own area to the
    // decimal: the limit itself is still a drop, and a hair more is not.
    const wide: Rect = { x: 4, y: 2, w: 10, h: 4 };
    expect(landed(wide, [{ x: 12, y: 2, w: 6, h: 4 }], BOARD, true)).toEqual({
      x: 2,
      y: 2,
      w: 10,
      h: 4,
    });
    expect(landed(wide, [{ x: 11.9, y: 2, w: 6, h: 4 }], BOARD, true)).toBe(
      null,
    );
  });

  it("counts every neighbour it landed on, not the worst one", () => {
    // An eighth each and a quarter together. Either alone is a drop; both at
    // once is a widget put down on top of the board rather than into a gap.
    const right = { x: 11, y: 2, w: 5, h: 4 };
    const left = { x: 0, y: 2, w: 5, h: 4 };
    expect(landed(WIDGET, [right], BOARD, true)).not.toBe(null);
    expect(landed(WIDGET, [left], BOARD, true)).not.toBe(null);
    expect(landed(WIDGET, [right, left], BOARD, true)).toBe(null);
  });

  it("goes sideways when the two ways out are the same length", () => {
    // A corner clipped: one column in and one row in. Rows are the scarcer of
    // the two on a 32x18 board, so a tie goes across.
    expect(landed(WIDGET, [{ x: 11, y: 5, w: 6, h: 4 }], BOARD, true)).toEqual({
      x: 3,
      y: 2,
      w: 8,
      h: 4,
    });
  });

  it("goes west when west and east are the same length", () => {
    // A column straddling the middle of a tall widget: four and a half cells
    // out either way, and eight cells out up or down. West is the top-left.
    const tall: Rect = { x: 10, y: 2, w: 8, h: 8 };
    expect(landed(tall, [{ x: 13.5, y: 2, w: 1, h: 8 }], BOARD, true)).toEqual({
      x: 5.5,
      y: 2,
      w: 8,
      h: 8,
    });
  });

  it("goes home when it was put squarely on top of something", () => {
    expect(landed(WIDGET, [{ ...WIDGET }], BOARD, true)).toBe(null);
  });
});

/**
 * A pocket: a gap with something on all four sides, so there is nowhere to
 * slide to and the only way to take the gap is to be smaller than it.
 */
const SIDE = { x: 0, y: 2, w: 4, h: 4 };
const ABOVE = { x: 0, y: 0, w: 32, h: 2 };
const BELOW = { x: 0, y: 6, w: 32, h: 2 };

describe("a drop into a gap slightly too small for it", () => {
  it("gives up the edge that is in the way, down to three quarters of itself", () => {
    // The neighbour takes two columns of the widget's top half — an eighth of
    // its area, so it is a drop — but there is nowhere to back out to, and
    // giving up those two columns costs a quarter of it exactly. The floor is
    // a floor, not a fence: standing on it is still a landing.
    const corner = { x: 10, y: 2, w: 6, h: 2 };
    expect(landed(WIDGET, [SIDE, ABOVE, BELOW, corner], BOARD, true)).toEqual({
      x: 4,
      y: 2,
      w: 6,
      h: 4,
    });
  });

  it("goes home rather than shrink past three quarters", () => {
    // A tenth of a column further in, so what is left is 23.6 cells of 32.
    // Below three quarters a widget starts saying less than it said: the VRAM
    // gauge abbreviates its own label, and it does it silently.
    const corner = { x: 9.9, y: 2, w: 6, h: 2 };
    expect(landed(WIDGET, [SIDE, ABOVE, BELOW, corner], BOARD, true)).toBe(
      null,
    );
  });

  it("goes home rather than shrink a widget already as small as one may be", () => {
    // In the corner of the board, so both ways out are off the board, and
    // already at `MIN_SIZE`, so there is nothing to give up either.
    const tiny: Rect = { x: 0, y: 0, w: MIN_SIZE, h: MIN_SIZE };
    const neighbour = { x: 0.21, y: 0, w: 4, h: MIN_SIZE };
    expect(landed(tiny, [neighbour], BOARD, true)).toBe(null);
  });
});

describe("what counts as a neighbour", () => {
  it("is the list it is handed and nothing else", () => {
    // Which is the whole of the rule for a page that is not showing and for
    // the widgets inside a folded group: the board draws `onBoard(onPage(...))`
    // and hands that same list to the drag, so a widget that is not on the
    // screen is not in the way. Here is the same drop, told and not told.
    const elsewhere = { x: 4, y: 2, w: 8, h: 4 };
    expect(landed(WIDGET, [], BOARD, true)).toEqual(WIDGET);
    expect(landed(WIDGET, [elsewhere], BOARD, true)).toBe(null);
  });
});
