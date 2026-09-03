/**
 * What a gesture means, without a browser.
 *
 * The board is a space rather than a set of slots, so this is where "the user
 * dragged the widget over there" turns into four numbers. Overlap is not asked
 * about here on purpose: the server owns that, and a refusal is what sends the
 * widget home.
 */
import { describe, expect, it } from "vitest";
import { dragged, same, MIN_SIZE, type Rect } from "@/lib/drag";

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
