import { describe, expect, it } from "vitest";
import type { MeshPart } from "@/lib/schemas/board";
import {
  BANDS,
  DEPTH_FADE,
  SPREAD,
  bandAt,
  camera,
  depthAt,
  fadeAt,
  layout,
  project,
  reachOf,
} from "@/lib/mesh";

function part(name: string, center: number[], verts: number[]): MeshPart {
  return { name, center, verts, edges: [] };
}

/** A camera looking straight on at a model half a unit across. */
const STRAIGHT = camera(0, 0, 200, 200, 0.5);

describe("layout", () => {
  // A part is a centre and the points around it; these have one point each, so
  // the model's radius is exactly where that point sits.
  const NEAR = part("near", [0, 0, 0.2], [0, 0, 0.2]);
  const FAR = part("far", [0, 0, 0.5], [0, 0, 0.5]);

  it("leaves an unexploded model alone", () => {
    const { moved, reach } = layout([NEAR, FAR], 0);
    expect(moved).toEqual([
      [0, 0, 0],
      [0, 0, 0],
    ]);
    expect(reach).toBeCloseTo(0.5);
  });

  it("spreads the outermost part against the model's own radius", () => {
    // Not a fixed distance: an exploded view has to fit the widget the
    // assembled one fitted, so what it is measured against has to be the model.
    const { moved } = layout([NEAR, FAR], 1);
    expect(Math.hypot(...moved[1])).toBeCloseTo(SPREAD * 0.5);
  });

  it("keeps the parts in the order they were assembled", () => {
    const { moved } = layout([NEAR, FAR], 1);
    expect(Math.hypot(...moved[0])).toBeCloseTo(Math.hypot(...moved[1]) * 0.4);
  });

  it("grows the reach, so an exploded model is drawn smaller to fit", () => {
    const assembled = layout([NEAR, FAR], 0).reach;
    const blown = layout([NEAR, FAR], 1).reach;
    expect(blown).toBeGreaterThan(assembled);
    // And not by so much that the parts stop being legible: the whole reason
    // the spread is measured against the radius rather than being a fixed 1.
    expect(blown).toBeLessThan(assembled * 2);
  });

  it("sends each part straight out from the middle", () => {
    const { moved } = layout([part("side", [3, 4, 0], [3, 4, 0])], 1);
    expect(moved[0][0] / moved[0][1]).toBeCloseTo(3 / 4);
  });

  it("cannot separate two parts that share a middle", () => {
    // Not a bug to fix in the arithmetic: concentric rings genuinely have the
    // same centre, so "away from the middle" is one direction for both. The
    // model has to give them different depths. See `tools/mesh/samples.py`.
    const rings = [
      part("ring", [0, 0, 0], [0.5, 0, 0]),
      part("coils", [0, 0, 0], [0.3, 0, 0]),
    ];
    expect(layout(rings, 1).moved).toEqual([
      [0, 0, 0],
      [0, 0, 0],
    ]);
  });

  it("survives a model that is one part sitting on the origin", () => {
    expect(layout([part("only", [0, 0, 0], [0, 0, 0])], 1).moved).toEqual([
      [0, 0, 0],
    ]);
  });
});

describe("reachOf", () => {
  it("is the furthest point plus how far its part has travelled", () => {
    const parts = [part("a", [0, 0, 0.5], [0, 0, 0.5])];
    expect(reachOf(parts, [[0, 0, 0]])).toBeCloseTo(0.5);
    expect(reachOf(parts, [[0, 0, 1]])).toBeCloseTo(1.5);
  });

  it("does not depend on the angle, so the model never breathes", () => {
    // Nothing in it reads the camera at all; this is the property being kept.
    const parts = [part("a", [0, 0, 0], [0.5, 0.5, 0.5, -0.5, -0.5, -0.5])];
    expect(reachOf(parts, [[0, 0, 0]])).toBeCloseTo(Math.hypot(0.5, 0.5, 0.5));
  });
});

describe("project", () => {
  it("puts the middle of the model in the middle of the widget", () => {
    const p = project(0, 0, 0, STRAIGHT);
    expect(p.sx).toBeCloseTo(100);
    expect(p.sy).toBeCloseTo(100);
  });

  it("counts screen y downward while the model counts up", () => {
    expect(project(0, 0.5, 0, STRAIGHT).sy).toBeLessThan(100);
  });

  it("draws a near point bigger than the same point far away", () => {
    const near = project(0.5, 0, 0.4, STRAIGHT);
    const far = project(0.5, 0, -0.4, STRAIGHT);
    expect(near.sx - 100).toBeGreaterThan(far.sx - 100);
  });

  it("turns the model about the upright axis", () => {
    // A quarter turn puts what was on +x onto -z: same distance out, but now
    // pointing away from the camera instead of to the right of it.
    const turned = camera(Math.PI / 2, 0, 200, 200, 0.5);
    const p = project(0.5, 0, 0, turned);
    expect(p.sx).toBeCloseTo(100);
    expect(p.depth).toBeCloseTo(-0.5);
  });

  it("brings the top of the model toward the camera when tilted", () => {
    const tilted = camera(0, 30, 200, 200, 0.5);
    expect(project(0, 0.5, 0, tilted).depth).toBeGreaterThan(0);
  });

  it("keeps the model inside the widget at every angle", () => {
    const reach = Math.hypot(0.5, 0.5, 0.5);
    for (let step = 0; step < 24; step++) {
      const cam = camera((step / 24) * Math.PI * 2, 20, 200, 120, reach);
      for (const x of [-0.5, 0.5])
        for (const y of [-0.5, 0.5])
          for (const z of [-0.5, 0.5]) {
            const p = project(x, y, z, cam);
            expect(p.sx).toBeGreaterThanOrEqual(0);
            expect(p.sx).toBeLessThanOrEqual(200);
            expect(p.sy).toBeGreaterThanOrEqual(0);
            expect(p.sy).toBeLessThanOrEqual(120);
          }
    }
  });

  it("does not divide by nothing when the model is a single point", () => {
    const p = project(0, 0, 0, camera(1, 20, 200, 200, 0));
    expect(Number.isFinite(p.sx)).toBe(true);
    expect(Number.isFinite(p.sy)).toBe(true);
  });
});

describe("depth", () => {
  it("runs from the back of the model to the front", () => {
    expect(depthAt(-0.5, 0.5)).toBeCloseTo(0);
    expect(depthAt(0.5, 0.5)).toBeCloseTo(1);
  });

  it("never dims an edge past the floor, or brightens one past full", () => {
    expect(fadeAt(-0.5, 0.5)).toBeCloseTo(DEPTH_FADE);
    expect(fadeAt(0.5, 0.5)).toBeCloseTo(1);
  });

  it("clamps a point that reaches further than the model was measured at", () => {
    expect(fadeAt(9, 0.5)).toBeCloseTo(1);
    expect(fadeAt(-9, 0.5)).toBeCloseTo(DEPTH_FADE);
  });

  it("sorts every depth into a band that exists", () => {
    for (const depth of [-9, -0.5, 0, 0.49, 0.5, 9]) {
      const band = bandAt(depth, 0.5);
      expect(band).toBeGreaterThanOrEqual(0);
      expect(band).toBeLessThan(BANDS);
      expect(Number.isInteger(band)).toBe(true);
    }
  });
});
