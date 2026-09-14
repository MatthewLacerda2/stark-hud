/**
 * Finding the largest size at which a word fits its box.
 *
 * This is the search; the measuring needs a browser and jsdom lays nothing
 * out. A box is stood in for by a size it stops fitting at.
 */
import { describe, expect, it } from "vitest";
import { largest } from "@/hooks/use-fit-text";

/** A box that holds anything up to `limit` and nothing over it. */
const upTo = (limit: number) => (size: number) => size <= limit;

describe("the largest size that fits", () => {
  it("takes the ceiling when the ceiling fits", () => {
    expect(largest(upTo(100), 40, 6)).toBe(40);
  });

  it("finds the size the box stops at, on a half-pixel grid", () => {
    expect(largest(upTo(17), 40, 6)).toBe(17);
    expect(largest(upTo(17.25), 40, 6)).toBe(17);
    expect(largest(upTo(17.5), 40, 6)).toBe(17.5);
  });

  it("settles for the floor when nothing fits, rather than drawing nothing", () => {
    expect(largest(upTo(2), 40, 6)).toBe(6);
  });

  it("does not go below the floor even when the ceiling is under it", () => {
    expect(largest(upTo(100), 4, 6)).toBe(6);
  });

  it("asks the box a handful of times, not once per size", () => {
    let asked = 0;
    largest((size) => (asked++, size <= 17), 40, 6);
    expect(asked).toBeLessThan(10);
  });
});
