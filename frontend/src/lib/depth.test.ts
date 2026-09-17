/**
 * The depth dials, and which way the board leans.
 *
 * The direction is the part worth pinning down. A lean that follows the pointer
 * instead of pushing away from it is a one-character mistake that still looks
 * like a 3D effect, just the wrong one, and nobody would notice from a sofa.
 */
import { describe, expect, it } from "vitest";
import { deep, depthFrom, lean, moving, recede } from "@/lib/depth";

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
