import { describe, expect, it } from "vitest";
import {
  FIT,
  SPREAD,
  colourFor,
  colourUp,
  explodeOffsets,
  fitDistance,
  formatOf,
  heading,
  phases,
  rampAt,
  type Vec3,
} from "@/lib/mesh";

describe("formatOf", () => {
  it("sends each kind of file to the loader that reads it", () => {
    expect(formatOf("/m/pc.glb")).toBe("gltf");
    expect(formatOf("/m/scene.GLTF")).toBe("gltf");
    expect(formatOf("/m/cloud.obj")).toBe("obj");
    expect(formatOf("/m/rig.fbx")).toBe("fbx");
  });

  it("names nothing for a file no loader here reads", () => {
    expect(formatOf("/m/pc.blend")).toBeNull();
  });
});

describe("fitDistance", () => {
  it("puts a sphere's edge on the view's edge, less the margin", () => {
    // 90 degrees square: the half-angle is 45, so the edge is r / sin 45 away.
    expect(fitDistance(1, 90, 1)).toBeCloseTo(Math.SQRT2 / FIT);
  });

  it("fits a wide widget to its height and a tall one to its width", () => {
    const wide = fitDistance(1, 40, 2);
    const square = fitDistance(1, 40, 1);
    const tall = fitDistance(1, 40, 0.5);
    expect(wide).toBeCloseTo(square);
    expect(tall).toBeGreaterThan(square);
  });
});

describe("explodeOffsets", () => {
  const CENTERS: Vec3[] = [
    [1, 0, 0],
    [0, 2, 0],
  ];

  it("leaves an assembled model where it is", () => {
    expect(explodeOffsets(CENTERS, 3, 0)).toEqual([
      [0, 0, 0],
      [0, 0, 0],
    ]);
  });

  it("moves each part out along its own line, the furthest the most", () => {
    const [near, far] = explodeOffsets(CENTERS, 3, 1);
    expect(near[0]).toBeGreaterThan(0);
    expect(far[1]).toBeCloseTo(SPREAD * 3);
    expect(far[1]).toBeGreaterThan(near[0]);
  });
});

describe("colourUp", () => {
  it("takes the nearest name any rule matches", () => {
    const rules = { gpu: "red", gpu_fan_1: "blue" };
    expect(colourUp(["blades", "gpu_fan_1", "gpu"], rules)).toBe("blue");
    expect(colourUp(["shroud", "gpu"], rules)).toBe("red");
  });

  it("says nothing when no name on the way up is ruled", () => {
    expect(colourUp(["case"], { gpu: "red" })).toBeNull();
  });
});

describe("phases", () => {
  const STACK = [[0, -1, 0] as Vec3, [0, 0, 0] as Vec3, [0, 1, 0] as Vec3];

  it("runs a stack wave from the lowest part to the highest", () => {
    expect(phases(STACK, "stack")).toEqual([0, 0.5, 1]);
  });

  it("pulses a flat model together rather than dividing by nothing", () => {
    const flat = [[1, 0, 0] as Vec3, [-1, 0, 0] as Vec3];
    expect(phases(flat, "stack")).toEqual([0, 0]);
  });

  it("runs a loop wave around the axis, in order", () => {
    const ring = [[1, 0, 0] as Vec3, [0, 0, 1] as Vec3, [-1, 0, 0] as Vec3];
    const [east, north, west] = phases(ring, "loop") as number[];
    expect(east).toBeCloseTo(0);
    expect(north).toBeCloseTo(0.25);
    expect(west).toBeCloseTo(0.5);
  });

  it("leaves a part standing on the axis out of a loop wave", () => {
    // Not a gap in the mode, but the useful half of it: on a model whose loop
    // is a ring of parts around a shaft, this lights the ring and leaves the
    // shaft at the widget's own colour.
    const ring = [[0, 0, 0] as Vec3, [1, 0, 0] as Vec3];
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

describe("heading", () => {
  it("goes round when there is no sweep", () => {
    expect(heading(0, 0.25, 0)).toBe(0);
    expect(heading(2, 0.25, 0)).toBeCloseTo(Math.PI);
    expect(heading(4, 0.25, 0)).toBeCloseTo(Math.PI * 2);
  });

  it("swings between the two ends of the sweep, and never past them", () => {
    const limit = (60 * Math.PI) / 180;
    for (let t = 0; t <= 40; t += 0.05) {
      const a = heading(t, 0.05, 60);
      expect(Math.abs(a)).toBeLessThanOrEqual(limit + 1e-9);
    }
    // One there-and-back per 1/spin seconds: 20s at 0.05.
    expect(heading(0, 0.05, 60)).toBeCloseTo(-limit);
    expect(heading(10, 0.05, 60)).toBeCloseTo(limit);
    expect(heading(20, 0.05, 60)).toBeCloseTo(-limit);
    expect(heading(5, 0.05, 60)).toBeCloseTo(0);
  });

  it("lingers at the ends and hurries through the middle", () => {
    const near = Math.abs(heading(1, 0.05, 60) - heading(0, 0.05, 60));
    const mid = Math.abs(heading(5.5, 0.05, 60) - heading(4.5, 0.05, 60));
    expect(near).toBeLessThan(mid / 10);
  });

  it("swings the other way for a negative spin, and holds still at zero", () => {
    expect(heading(10, -0.05, 60)).toBeCloseTo(-(60 * Math.PI) / 180);
    expect(heading(10, 0, 60)).toBe(0);
  });
});
