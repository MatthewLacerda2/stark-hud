/**
 * Where the call that made a widget goes, as arithmetic.
 *
 * The rule it has to keep is the one nothing else on this board is allowed to
 * break either: whatever the widget's shape or wherever it sits, the panel is
 * entirely on the screen. A HUD that lets something hang off the edge for two
 * seconds has just put a fault on the television.
 */
import { describe, expect, it } from "vitest";
import { beside } from "@/lib/origin";

const BOARD = { cols: 32, rows: 18 };

/** The panel is a quarter of the board wide and a ninth of it tall. */
const W = 8;
const H = 2;

describe("the call beside a widget", () => {
  it("sits on the side with the room, and is always that size", () => {
    const seat = beside({ x: 2, y: 4, w: 4, h: 4 }, BOARD);

    // Twenty-six columns to its right against two to its left.
    expect(seat).toEqual({ x: 6, y: 4, w: W, h: H });
  });

  it("goes to the other side when that is the emptier one", () => {
    const seat = beside({ x: 20, y: 4, w: 4, h: 4 }, BOARD);

    // Twenty to the left against eight to the right: both fit, the left is
    // roomier, and a call in open space reads better than one in a gap.
    expect(seat.x).toBe(12);
  });

  it("takes the only side that fits, roomy or not", () => {
    // Eight columns to the left exactly, and none at all to the right.
    const seat = beside({ x: 8, y: 4, w: 24, h: 4 }, BOARD);

    expect(seat.x).toBe(0);
  });

  it("lies over the widget when neither side can hold it", () => {
    const seat = beside({ x: 4, y: 4, w: 26, h: 4 }, BOARD);

    // Centred on the widget, which is where it is least in the way of itself.
    expect(seat.x).toBe(13);
  });

  it("never leaves the screen, whatever it is beside", () => {
    const rects = [
      { x: 0, y: 0, w: 1, h: 1 },
      { x: 31, y: 17, w: 1, h: 1 },
      { x: 0, y: 16, w: 32, h: 2 },
      { x: 14, y: 17, w: 4, h: 1 },
      { x: 0, y: 0, w: 32, h: 18 },
    ];

    for (const rect of rects) {
      const seat = beside(rect, BOARD);
      expect(seat.x).toBeGreaterThanOrEqual(0);
      expect(seat.y).toBeGreaterThanOrEqual(0);
      expect(seat.x + seat.w).toBeLessThanOrEqual(BOARD.cols);
      expect(seat.y + seat.h).toBeLessThanOrEqual(BOARD.rows);
    }
  });

  it("is level with the widget's top until the bottom of the board", () => {
    expect(beside({ x: 2, y: 7, w: 4, h: 4 }, BOARD).y).toBe(7);
    // Level with a widget at the very bottom would put half of it off-screen.
    expect(beside({ x: 2, y: 17, w: 4, h: 1 }, BOARD).y).toBe(16);
  });
});
