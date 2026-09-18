/** Zooming about a point keeps that point where it was. */
import { describe, expect, it } from "vitest";
import { WHOLE, wheelFactor, zoomAt } from "@/lib/zoom";

/** Where the picture's point under `(px, py)` ends up on screen after `view`. */
function under(view: { scale: number; x: number; y: number }, px: number) {
  return (px - view.x) / view.scale;
}

describe("zoomAt", () => {
  it("keeps the point under the pointer under the pointer", () => {
    const once = zoomAt(WHOLE, 2, 300, 200);
    const twice = zoomAt(once, 1.5, 120, 80);
    expect(under(once, 300)).toBeCloseTo(under(WHOLE, 300));
    expect(under(twice, 120)).toBeCloseTo(under(once, 120));
  });

  it("never zooms out past the whole picture, and snaps back to it", () => {
    expect(zoomAt({ scale: 1.2, x: -50, y: -30 }, 0.5, 10, 10)).toEqual(WHOLE);
  });

  it("stops at twenty times", () => {
    expect(zoomAt(WHOLE, 100, 0, 0).scale).toBe(20);
  });
});

describe("wheelFactor", () => {
  it("zooms in on a wheel pushed away and out on one pulled back", () => {
    expect(wheelFactor(-100)).toBeGreaterThan(1);
    expect(wheelFactor(100)).toBeLessThan(1);
  });
});
