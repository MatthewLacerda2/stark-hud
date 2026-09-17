/**
 * The depth dials, and which way the board leans.
 *
 * The direction is the part worth pinning down. A lean that follows the pointer
 * instead of pushing away from it is a one-character mistake that still looks
 * like a 3D effect, just the wrong one, and nobody would notice from a sofa.
 */
import { describe, expect, it } from "vitest";
import {
  deep,
  depthFrom,
  farther,
  lean,
  leanShift,
  moving,
  recede,
  seatVars,
} from "@/lib/depth";

const CENTRE = { x: 0, y: 0 };

describe("how much of the board is glass in a room", () => {
  it("is the settled look when nobody asked", () => {
    // Half the glass, a nudge of tilt, and no sway: what was chosen at the
    // television. A board nobody touches must hold still.
    expect(depthFrom("")).toEqual({ tilt: 0.1, sway: 0, glass: 0.5 });
    expect(depthFrom("?vhs=1&bloom=1")).toEqual(depthFrom(""));
  });

  it("is none of it when the master is zero", () => {
    expect(deep(depthFrom("?depth=0"))).toBe(false);
  });

  it("scales every part together with the master", () => {
    expect(depthFrom("?depth=1")).toEqual({ tilt: 0.2, sway: 0, glass: 1 });
  });

  it("lets one part be turned off while the rest stay on", () => {
    const depth = depthFrom("?depth=1&sway=0");
    expect(depth.sway).toBe(0);
    expect(depth.glass).toBe(1);
    expect(moving(depth)).toBe(true);
  });

  it("scales a named part by the master, so zero really is off", () => {
    expect(deep(depthFrom("?depth=0&glass=1&tilt=1"))).toBe(false);
    expect(depthFrom("?depth=0.5&glass=0.4").glass).toBeCloseTo(0.2);
  });

  it("survives whatever gets typed on the way to a number", () => {
    expect(depthFrom("?depth=banana")).toEqual(depthFrom(""));
    expect(depthFrom("?depth=7").glass).toBe(1);
    expect(depthFrom("?depth=1&tilt=-3").tilt).toBe(0);
  });

  it("does not move when there is glass but no lean", () => {
    expect(moving(depthFrom("?depth=1&tilt=0&sway=0"))).toBe(false);
  });
});

describe("which way the board leans", () => {
  const tiltOnly = depthFrom("?depth=1&sway=0");

  it("sits level with the pointer in the middle and no sway", () => {
    const turned = lean(tiltOnly, CENTRE, 12);
    expect(turned.x).toBeCloseTo(0);
    expect(turned.y).toBeCloseTo(0);
  });

  it("pushes the right side back when the pointer is on the right", () => {
    // rotateY positive carries +x into -z: away from the viewer.
    expect(lean(tiltOnly, { x: 1, y: 0 }, 0).y).toBeGreaterThan(0);
  });

  it("pushes the top back when the pointer is near the top", () => {
    // rotateX positive carries -y (up, in CSS) into -z.
    expect(lean(tiltOnly, { x: 0, y: -1 }, 0).x).toBeGreaterThan(0);
  });

  it("sways on its own, and never far", () => {
    const swayOnly = depthFrom("?depth=1&tilt=0&sway=1");
    const seen = Array.from({ length: 600 }, (_, second) =>
      lean(swayOnly, CENTRE, second),
    );
    const widest = Math.max(
      ...seen.map((turned) => Math.max(Math.abs(turned.x), Math.abs(turned.y))),
    );
    expect(widest).toBeGreaterThan(0.3);
    expect(widest).toBeLessThanOrEqual(1.2);
  });
});

describe("keeping the near corner on the screen", () => {
  it("pushes nothing back when the board is level", () => {
    expect(recede({ x: 0, y: 0 }, 1920, 1080)).toBe(0);
  });

  it("pushes back as far as the near side came forward", () => {
    // Turned about the upright axis, the near edge is half the width out and
    // comes forward by that times the sine of the turn.
    const back = recede({ x: 0, y: 5 }, 1920, 1080);
    expect(back).toBeCloseTo(960 * Math.sin((5 * Math.PI) / 180));
  });
});

describe("how far something behind a widget's face moves", () => {
  const board = { cols: 32, rows: 18, width: 1920, height: 1080 };
  const at = (x: number, y: number) =>
    seatVars(
      { x, y, w: 2, h: 2 },
      board.cols,
      board.rows,
      board.width,
      board.height,
    ) as Record<string, number>;

  it("does not move in the middle of the board", () => {
    expect(at(15, 8)["--seat-x"]).toBeCloseTo(0);
    expect(at(15, 8)["--seat-y"]).toBeCloseTo(0);
  });

  it("moves towards the middle, the way the walls open", () => {
    // Top left: depth pulls it right and down, towards the vanishing point.
    expect(at(0, 0)["--seat-x"]).toBeGreaterThan(0);
    expect(at(0, 0)["--seat-y"]).toBeGreaterThan(0);
    expect(at(30, 16)["--seat-x"]).toBeLessThan(0);
  });

  it("says nothing before the board has been measured", () => {
    expect(seatVars({ x: 0, y: 0, w: 2, h: 2 }, 32, 18, 0, 0)).toEqual({});
  });
});

describe("how far the lean moves something behind the face", () => {
  it("is nothing when level", () => {
    const shift = leanShift({ x: 0, y: 0 });
    expect(shift.x).toBeCloseTo(0);
    expect(shift.y).toBeCloseTo(0);
  });

  it("swings against the side that recedes", () => {
    // Right side back: a point behind the face slides left.
    expect(leanShift({ x: 0, y: 5 }).x).toBeLessThan(0);
    // Top back: a point behind the face drops.
    expect(leanShift({ x: 5, y: 0 }).y).toBeGreaterThan(0);
  });
});

describe("how much smaller the back of a mark is drawn", () => {
  it("is the face itself at no depth", () => {
    expect(farther(0, 1920, 1080)).toBe(1);
  });

  it("shrinks further the deeper it goes, and never by much", () => {
    const near = farther(0.5, 1920, 1080);
    const far = farther(1.25, 1920, 1080);
    expect(far).toBeLessThan(near);
    expect(far).toBeGreaterThan(0.95);
  });
});
