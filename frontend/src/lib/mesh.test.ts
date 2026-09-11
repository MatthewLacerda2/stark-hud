import { describe, expect, it } from "vitest";
import type { MeshPart } from "@/lib/schemas/board";
import {
  BANDS,
  DEPTH_FADE,
  FIT,
  SPREAD,
  bandAt,
  boundsOf,
  camera,
  colourFor,
  depthAt,
  fadeAt,
  layout,
  phases,
  project,
  rampAt,
  reachOf,
} from "@/lib/mesh";

function part(name: string, center: number[], verts: number[]): MeshPart {
  return { name, center, verts, edges: [] };
}

/** The eight corners of a cube half a unit out from the middle. */
const CUBE = part(
  "cube",
  [0, 0, 0],
  [-0.5, -0.5, -0.5, 0.5, 0.5, 0.5, -0.5, 0.5, -0.5, 0.5, -0.5, 0.5],
);
const STILL: [number, number, number][] = [[0, 0, 0]];

/** A camera looking straight on at a model half a unit across. */
const STRAIGHT = camera(0, 0, 200, 200, {
  radial: 0.5,
  vertical: 0.5,
  depth: 0.5,
});

describe("layout", () => {
  // A part is a centre and the points around it; these have one point each, so
  // the model's radius is exactly where that point sits.
  const NEAR = part("near", [0, 0, 0.2], [0, 0, 0.2]);
  const FAR = part("far", [0, 0, 0.5], [0, 0, 0.5]);

  it("leaves an unexploded model alone", () => {
    expect(layout([NEAR, FAR], 0, 0).moved).toEqual([
      [0, 0, 0],
      [0, 0, 0],
    ]);
  });

  it("spreads the outermost part against the model's own radius", () => {
    // Not a fixed distance: an exploded view has to fit the widget the
    // assembled one fitted, so what it is measured against has to be the model.
    const { moved } = layout([NEAR, FAR], 1, 0);
    expect(Math.hypot(...moved[1])).toBeCloseTo(SPREAD * 0.5);
  });

  it("keeps the parts in the order they were assembled", () => {
    const { moved } = layout([NEAR, FAR], 1, 0);
    expect(Math.hypot(...moved[0])).toBeCloseTo(Math.hypot(...moved[1]) * 0.4);
  });

  it("reaches further once exploded, so the model is drawn smaller to fit", () => {
    expect(layout([NEAR, FAR], 1, 0).bounds.vertical).toBeGreaterThanOrEqual(
      layout([NEAR, FAR], 0, 0).bounds.vertical,
    );
  });

  it("sends each part straight out from the middle", () => {
    const { moved } = layout([part("side", [3, 4, 0], [3, 4, 0])], 1, 0);
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
    expect(layout(rings, 1, 0).moved).toEqual([
      [0, 0, 0],
      [0, 0, 0],
    ]);
  });

  it("survives a model that is one part sitting on the origin", () => {
    expect(layout([part("only", [0, 0, 0], [0, 0, 0])], 1, 0).moved).toEqual([
      [0, 0, 0],
    ]);
  });
});

describe("boundsOf", () => {
  it("measures across the axis, not through the corners", () => {
    // The whole point of measuring per axis. A bounding sphere would call this
    // cube 0.87 wide because that is its diagonal; spinning only ever swings a
    // point around a circle, and the widest of those is 0.71.
    const flat = boundsOf([CUBE], STILL, 0);
    expect(flat.radial).toBeCloseTo(Math.hypot(0.5, 0.5));
    expect(flat.radial).toBeLessThan(reachOf([CUBE], STILL));
  });

  it("leaves height alone when the camera is level", () => {
    expect(boundsOf([CUBE], STILL, 0).vertical).toBeCloseTo(0.5);
  });

  it("grows the height as the camera tilts, because the model leans", () => {
    expect(boundsOf([CUBE], STILL, 30).vertical).toBeGreaterThan(0.5);
  });

  it("does not depend on the angle, so the model never breathes", () => {
    // Nothing in it reads the spin at all; this is the property being kept.
    const spun = part("a", [0, 0, 0], [0.4, 0.1, 0, 0, 0.1, 0.4]);
    expect(boundsOf([spun], STILL, 20).radial).toBeCloseTo(0.4);
  });
});

describe("camera", () => {
  it("fills a tall widget using its height, not its width", () => {
    // The bug this replaced: fitting to min(width, height) drew a tall model
    // inside the short side and wasted the rest of the widget.
    const bounds = { radial: 0.2, vertical: 0.5, depth: 0.3 };
    const tall = camera(0, 0, 200, 600, bounds);
    const square = camera(0, 0, 200, 200, bounds);
    expect(tall.scale).toBeGreaterThan(square.scale);
  });

  it("stops at whichever axis runs out first", () => {
    const wide = camera(0, 0, 200, 600, {
      radial: 0.9,
      vertical: 0.1,
      depth: 0.2,
    });
    // Width-limited: the model is far wider than it is tall, so making the
    // widget taller must not make the drawing any bigger.
    expect(wide.scale).toBeCloseTo(
      camera(0, 0, 200, 9000, { radial: 0.9, vertical: 0.1, depth: 0.2 }).scale,
    );
  });

  it("does not divide by nothing when the model is a single point", () => {
    const p = project(0, 0, 0, camera(1, 20, 200, 200, STRAIGHT_POINT));
    expect(Number.isFinite(p.sx)).toBe(true);
    expect(Number.isFinite(p.sy)).toBe(true);
  });
});

const STRAIGHT_POINT = { radial: 0, vertical: 0, depth: 0 };

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
    expect(project(0.5, 0, 0.4, STRAIGHT).sx - 100).toBeGreaterThan(
      project(0.5, 0, -0.4, STRAIGHT).sx - 100,
    );
  });

  it("turns the model about the upright axis", () => {
    // A quarter turn puts what was on +x onto -z: same distance out, but now
    // pointing away from the camera instead of to the right of it.
    const turned = camera(Math.PI / 2, 0, 200, 200, {
      radial: 0.5,
      vertical: 0.5,
      depth: 0.5,
    });
    const p = project(0.5, 0, 0, turned);
    expect(p.sx).toBeCloseTo(100);
    expect(p.depth).toBeCloseTo(-0.5);
  });

  it("brings the top of the model toward the camera when tilted", () => {
    const tilted = camera(0, 30, 200, 200, {
      radial: 0.5,
      vertical: 0.6,
      depth: 0.6,
    });
    expect(project(0, 0.5, 0, tilted).depth).toBeGreaterThan(0);
  });

  it("keeps the model inside the widget at every angle", () => {
    // The guarantee the whole fit exists for: nothing may overlap on this
    // board, so no line may leave its widget however the model is turned.
    const bounds = boundsOf([CUBE], STILL, 20);
    for (let step = 0; step < 24; step++) {
      const cam = camera((step / 24) * Math.PI * 2, 20, 200, 120, bounds);
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

  it("uses most of the widget it is given", () => {
    // The other half of the same guarantee. Staying inside is easy if you draw
    // small, and drawing small is exactly what the old single-radius fit did —
    // so containment alone would have passed the bug that prompted this.
    //
    // It cannot reach FIT exactly: the scale is solved for the nearest point
    // the model could ever swing to, and the point furthest to the side is not
    // that point, so a little margin is inherent rather than wasteful.
    const bounds = boundsOf([CUBE], STILL, 0);
    let widest = 0;
    for (let step = 0; step < 24; step++) {
      const cam = camera((step / 24) * Math.PI * 2, 0, 200, 200, bounds);
      for (const x of [-0.5, 0.5])
        for (const z of [-0.5, 0.5])
          widest = Math.max(widest, Math.abs(project(x, 0.5, z, cam).sx - 100));
    }
    expect(widest).toBeGreaterThan(100 * FIT * 0.8);
    expect(widest).toBeLessThanOrEqual(100);
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

  it("clamps a point reaching further than the model was measured at", () => {
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

describe("phases", () => {
  const STACK = [
    part("bottom", [0, -1, 0], []),
    part("middle", [0, 0, 0], []),
    part("top", [0, 1, 0], []),
  ];

  it("runs a stack wave from the lowest part to the highest", () => {
    expect(phases(STACK, "stack")).toEqual([0, 0.5, 1]);
  });

  it("pulses a flat model together rather than dividing by nothing", () => {
    const flat = [part("a", [1, 0, 0], []), part("b", [-1, 0, 0], [])];
    expect(phases(flat, "stack")).toEqual([0, 0]);
  });

  it("runs a loop wave around the axis, in order", () => {
    const ring = [
      part("east", [1, 0, 0], []),
      part("north", [0, 0, 1], []),
      part("west", [-1, 0, 0], []),
    ];
    const [east, north, west] = phases(ring, "loop") as number[];
    expect(east).toBeCloseTo(0);
    expect(north).toBeCloseTo(0.25);
    expect(west).toBeCloseTo(0.5);
  });

  it("leaves a part standing on the axis out of a loop wave", () => {
    // Not a gap in the mode, but the useful half of it: on a model whose loop
    // is a ring of parts around a shaft, this lights the ring and leaves the
    // shaft at the widget's own colour.
    const ring = [part("shaft", [0, 0, 0], []), part("petal", [1, 0, 0], [])];
    expect(phases(ring, "loop")[0]).toBeNull();
    expect(phases(ring, "loop")[1]).not.toBeNull();
  });
});

describe("rampAt", () => {
  it("walks the colours in order as it goes", () => {
    // Not tested on a boundary: 1/3 times 3 is not 1 in floating point, so
    // which stretch that lands in is a coin-toss and says nothing about this.
    expect(rampAt(3, 0)).toEqual({ from: 0, to: 1, mix: 0 });
    expect(rampAt(3, 0.4)).toMatchObject({ from: 1, to: 2 });
    expect(rampAt(3, 0.8)).toMatchObject({ from: 2, to: 0 });
  });

  it("wraps the last colour back into the first", () => {
    // What makes a three-colour list a cycle rather than a journey that has to
    // jump home. Somebody wanting it to come back the way it went says so by
    // writing the middle colour twice.
    expect(rampAt(3, 2 / 3 + 0.001).to).toBe(0);
  });

  it("takes a position anywhere on the number line", () => {
    for (const t of [-9.25, -0.5, 0, 0.5, 12.75]) {
      const at = rampAt(4, t);
      expect(at.from).toBeGreaterThanOrEqual(0);
      expect(at.from).toBeLessThan(4);
      expect(at.mix).toBeGreaterThanOrEqual(0);
      expect(at.mix).toBeLessThan(1);
    }
  });
});

describe("colourFor", () => {
  it("matches a part by name", () => {
    expect(colourFor("embed", { embed: "accent" })).toBe("accent");
  });

  it("matches a glob across many parts", () => {
    expect(colourFor("encoder_3", { "encoder_*": "chart-2" })).toBe("chart-2");
  });

  it("lets the longest pattern win, whatever order they were written in", () => {
    // So a name always beats a wildcard without anybody having to think about
    // which rule they wrote first.
    const rules = { "*": "muted", "encoder_*": "chart-2", encoder_3: "accent" };
    expect(colourFor("encoder_3", rules)).toBe("accent");
    expect(colourFor("encoder_4", rules)).toBe("chart-2");
    expect(colourFor("head", rules)).toBe("muted");
  });

  it("anchors a glob at both ends", () => {
    expect(colourFor("my_encoder_3", { "encoder_*": "chart-2" })).toBeNull();
  });

  it("says nothing when a widget names no colours at all", () => {
    expect(colourFor("embed", null)).toBeNull();
    expect(colourFor("embed", {})).toBeNull();
  });
});
