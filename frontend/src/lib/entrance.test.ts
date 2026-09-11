/**
 * The corridor test, which is the whole of the craft in an arrival.
 *
 * Everything here is rectangles on the board's own 32x18 grid, because that is
 * all the answer depends on: what the widget is, what it draws and how long the
 * flight takes are somebody else's questions.
 */
import { describe, expect, it } from "vitest";
import type { Rect } from "@/lib/drag";
import { entrance, entranceClass, entranceVars } from "@/lib/entrance";

const BOARD = { cols: 32, rows: 18 };

function at(x: number, y: number, w: number, h: number): Rect {
  return { x, y, w, h };
}

/** A 4x4 widget in the middle, with something in the way on all four sides. */
const MIDDLE = at(14, 7, 4, 4);
const WEST = at(5, 7, 2, 4);
const EAST = at(25, 7, 2, 4);
const NORTH = at(14, 2, 4, 2);
const SOUTH = at(14, 15, 4, 2);

describe("entrance", () => {
  it("flies in from the nearest edge when the board is empty", () => {
    // Six columns to the left wall, nine rows to the top, and much further to
    // the other two, so it comes in from the west.
    const flight = entrance(at(2, 5, 4, 4), [], BOARD);
    expect(flight.edge).toBe("w");
    // Six columns of travel is one and a half of its own four-column width.
    expect(flight.dx).toBeCloseTo(-1.5);
    expect(flight.dy).toBe(0);
  });

  it("measures a fractional widget in its own fractional sizes", () => {
    const flight = entrance(at(1.5, 6, 4.5, 3), [], BOARD);
    expect(flight.edge).toBe("w");
    expect(flight.dx).toBeCloseTo(-(1.5 + 4.5) / 4.5);
  });

  it("grows in place when it is boxed in on all four sides", () => {
    const flight = entrance(MIDDLE, [WEST, EAST, NORTH, SOUTH], BOARD);
    expect(flight.edge).toBeNull();
    expect(flight).toEqual({ edge: null, dx: 0, dy: 0 });
  });

  it("takes the one edge that is clear, however far away it is", () => {
    // South is the longest of the four corridors from here and the only open
    // one, so it is the one taken: a flight beats growing out of nothing.
    const flight = entrance(MIDDLE, [WEST, EAST, NORTH], BOARD);
    expect(flight.edge).toBe("s");
    expect(flight.dy).toBeCloseTo((18 - 7) / 4);
    expect(flight.dx).toBe(0);
  });

  it("takes the nearer of two clear edges, not the first one it tests", () => {
    // North is sixteen rows away and south is six. North is tested first, and
    // has to lose anyway.
    const low = at(14, 12, 4, 4);
    const flight = entrance(low, [at(5, 12, 2, 4), at(25, 12, 2, 4)], BOARD);
    expect(flight.edge).toBe("s");
    expect(flight.dy).toBeCloseTo(6 / 4);
  });

  it("breaks a tie between west and east by taking west", () => {
    // Centred on the board, so the two horizontal corridors are exactly as long
    // as each other. The vertical pair is nearer, so it is blocked off.
    const flight = entrance(MIDDLE, [NORTH, SOUTH], BOARD);
    expect(flight.edge).toBe("w");
    expect(flight.dx).toBeCloseTo(-18 / 4);
  });

  it("breaks a tie between north and south by taking north", () => {
    const flight = entrance(MIDDLE, [WEST, EAST], BOARD);
    expect(flight.edge).toBe("n");
    expect(flight.dy).toBeCloseTo(-11 / 4);
  });

  it("is the same answer every time, whatever order the board comes in", () => {
    const once = entrance(MIDDLE, [WEST, EAST, NORTH], BOARD);
    const again = entrance(MIDDLE, [NORTH, EAST, WEST], BOARD);
    const third = entrance(MIDDLE, [EAST, WEST, NORTH], BOARD);
    expect(again).toEqual(once);
    expect(third).toEqual(once);
  });

  it("is not blocked by a widget that only touches the corridor", () => {
    // The corridor west of this widget is rows 5 to 9. This one starts at 9,
    // shares an edge with it and no area at all, so the way is still clear.
    const flight = entrance(at(2, 5, 4, 4), [at(0, 9, 6, 2)], BOARD);
    expect(flight.edge).toBe("w");
  });

  it("is blocked by a widget that is only partly in the way", () => {
    // A single row of overlap is a widget the flight would pass over.
    const flight = entrance(at(2, 5, 4, 4), [at(0, 8, 6, 2)], BOARD);
    expect(flight.edge).not.toBe("w");
  });
});

describe("entranceVars", () => {
  it("gives the flight's start as a share of the widget's own size", () => {
    expect(entranceVars({ edge: "w", dx: -1.5, dy: 0 })).toEqual({
      "--fly-x": "-150.00%",
      "--fly-y": "0.00%",
    });
  });
});

describe("entranceClass", () => {
  it("flies a widget with a corridor in, and back out the same way", () => {
    const flight = { edge: "n", dx: 0, dy: -2 } as const;
    expect(entranceClass(flight, false)).toBe("widget-flying-in");
    expect(entranceClass(flight, true)).toBe("widget-flying-out");
  });

  it("grows a boxed-in widget in place, and shrinks it there too", () => {
    const flight = { edge: null, dx: 0, dy: 0 } as const;
    expect(entranceClass(flight, false)).toBe("widget-arriving");
    expect(entranceClass(flight, true)).toBe("widget-leaving");
  });
});
