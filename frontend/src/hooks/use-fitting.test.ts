/**
 * How many rows fit whole in a box.
 *
 * Nobody can scroll this screen, so a list longer than its widget loses the
 * tail — and losing it mid-row reads as a fault rather than as a boundary. This
 * is the counting; the measuring needs a browser and jsdom lays nothing out.
 */
import { describe, expect, it } from "vitest";
import { fitting, type Row } from "@/hooks/use-fitting";

/** Four rows of 20px, stacked from the top. */
const ROWS: Row[] = [0, 20, 40, 60].map((top) => ({ top, height: 20 }));

describe("counting the rows that fit", () => {
  it("takes every row when there is room for all of them", () => {
    expect(fitting(ROWS, 80)).toBe(4);
    expect(fitting(ROWS, 500)).toBe(4);
  });

  it("stops before the row that would be cut across the middle", () => {
    expect(fitting(ROWS, 50)).toBe(2);
    expect(fitting(ROWS, 78)).toBe(3);
  });

  it("takes a row that ends exactly on the edge", () => {
    expect(fitting(ROWS, 40)).toBe(2);
  });

  it("forgives a pixel, so sub-pixel layout does not cost a whole row", () => {
    expect(fitting([{ top: 0, height: 20.6 }], 20)).toBe(1);
    expect(fitting([{ top: 0, height: 22 }], 20)).toBe(0);
  });

  it("takes nothing when there is room for nothing", () => {
    expect(fitting(ROWS, 0)).toBe(0);
    expect(fitting([], 100)).toBe(0);
  });
});
