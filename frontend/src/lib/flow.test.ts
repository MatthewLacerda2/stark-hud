/**
 * Reading a flow: where the boxes land, where the arrows meet them, and when a
 * word is dropped off one.
 *
 * The widget's shape is stated rather than measured, so every one of these is a
 * fact about the arithmetic and not about a browser that is not running. What
 * cannot be checked here is how any of it looks — that is a television.
 */
import { describe, expect, it } from "vitest";
import type { FlowLink, FlowNode } from "@/lib/schemas/board";
import type { Point } from "@/lib/flow";
import {
  anchor,
  boxes,
  cells,
  facing,
  LINE_CROSS,
  LINE_FILL,
  midpoint,
  roomy,
  route,
} from "@/lib/flow";

function node(id: string, box?: Partial<FlowNode>): FlowNode {
  return {
    id,
    text: id,
    shape: "rectangle",
    radius: 0.18,
    color: null,
    x: null,
    y: null,
    w: null,
    h: null,
    ...box,
  };
}

function link(
  source: string,
  target: string,
  over?: Partial<FlowLink>,
): FlowLink {
  return {
    source,
    target,
    source_side: null,
    target_side: null,
    label: null,
    curve: "straight",
    heads: "end",
    color: null,
    ...over,
  };
}

/**
 * A point, to the nearest ten-thousandth of the widget.
 *
 * These fractions are sums of tenths, so `0.7 + 0.1` is `0.7999999999999999`
 * and an exact comparison would be testing IEEE 754 rather than the geometry.
 * Four places is far finer than a pixel on any television.
 */
function near(at: Point) {
  return { x: Math.round(at.x * 1e4) / 1e4, y: Math.round(at.y * 1e4) / 1e4 };
}

const WIDE = { cols: 12, rows: 4 };
const TALL = { cols: 4, rows: 12 };

describe("where the boxes land", () => {
  it("puts a node exactly where it said it sits", () => {
    const placed = boxes(
      [node("build", { x: 0.1, y: 0.2, w: 0.3, h: 0.4 })],
      WIDE.cols,
      WIDE.rows,
    );

    expect(placed.get("build")).toEqual({ x: 0.1, y: 0.2, w: 0.3, h: 0.4 });
  });

  it("lays an unplaced flow out along the widget's longer side", () => {
    const placed = boxes(
      [node("a"), node("b"), node("c")],
      WIDE.cols,
      WIDE.rows,
    );
    const along = ["a", "b", "c"].map((id) => placed.get(id)!);

    // Three equal slots across, every box the same size and the same distance
    // down: one line, evenly spaced, uniformly sized.
    expect(along.map((box) => box.w)).toEqual([
      LINE_FILL / 3,
      LINE_FILL / 3,
      LINE_FILL / 3,
    ]);
    expect(new Set(along.map((box) => box.y))).toEqual(
      new Set([(1 - LINE_CROSS) / 2]),
    );
    expect(along[0].x).toBeLessThan(along[1].x);
    expect(along[1].x).toBeLessThan(along[2].x);
  });

  it("turns that line down the widget when the widget is taller than it is wide", () => {
    const placed = boxes([node("a"), node("b")], TALL.cols, TALL.rows);
    const down = ["a", "b"].map((id) => placed.get(id)!);

    expect(down.map((box) => box.h)).toEqual([LINE_FILL / 2, LINE_FILL / 2]);
    expect(down[0].y).toBeLessThan(down[1].y);
    expect(down[0].x).toBe(down[1].x);
  });

  it("keeps every box it lays out inside the widget", () => {
    for (const count of [1, 2, 5, 9]) {
      const nodes = Array.from({ length: count }, (_, at) => node(`n${at}`));
      for (const box of boxes(nodes, WIDE.cols, WIDE.rows).values()) {
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.y).toBeGreaterThanOrEqual(0);
        expect(box.x + box.w).toBeLessThanOrEqual(1);
        expect(box.y + box.h).toBeLessThanOrEqual(1);
      }
    }
  });
});

const LEFT = { x: 0.1, y: 0.4, w: 0.2, h: 0.2 };
const RIGHT = { x: 0.7, y: 0.4, w: 0.2, h: 0.2 };
const BELOW = { x: 0.1, y: 0.7, w: 0.2, h: 0.2 };

describe("where an arrow meets a box", () => {
  it("meets the side it was told to, whatever the other box is doing", () => {
    const run = route(
      LEFT,
      RIGHT,
      link("a", "b", { source_side: "top", target_side: "bottom" }),
    );

    expect(near(run.start)).toEqual({ x: 0.2, y: 0.4 });
    expect(near(run.end)).toEqual({ x: 0.8, y: 0.6 });
  });

  it("picks the pair of facing sides when it was told neither", () => {
    expect(facing(LEFT, RIGHT)).toEqual(["right", "left"]);
    expect(facing(RIGHT, LEFT)).toEqual(["left", "right"]);
    expect(facing(LEFT, BELOW)).toEqual(["bottom", "top"]);
    expect(facing(BELOW, LEFT)).toEqual(["top", "bottom"]);
  });

  it("routes a straight arrow between those facing sides", () => {
    const run = route(LEFT, RIGHT, link("a", "b"));

    expect(near(run.start)).toEqual({ x: 0.3, y: 0.5 });
    expect(near(run.end)).toEqual({ x: 0.7, y: 0.5 });
    expect(run.control).toBeNull();
    expect(run.atEnd).toEqual({ x: 1, y: 0 });
  });

  it("puts an ellipse's anchor where a rectangle's is, because the two touch there", () => {
    // The ellipse inscribed in a box touches it at the midpoints of its sides,
    // so the shape never enters the arithmetic.
    expect(near(anchor(LEFT, "right"))).toEqual({ x: 0.3, y: 0.5 });
    expect(near(anchor(LEFT, "center"))).toEqual({ x: 0.2, y: 0.5 });
  });
});

describe("the S", () => {
  it("leaves and arrives along the sides it meets, not along the run", () => {
    const run = route(LEFT, RIGHT, link("a", "b", { curve: "s" }));

    expect(run.control).not.toBeNull();
    // Both control points sit level with their own end, which is what makes the
    // line leave rightward and arrive leftward instead of cutting the diagonal.
    expect(run.control![0].y).toBe(run.start.y);
    expect(run.control![1].y).toBe(run.end.y);
    expect(run.control![0].x).toBeGreaterThan(run.start.x);
    expect(run.control![1].x).toBeLessThan(run.end.x);
  });

  it("bows out of a named side even when the run is the other way", () => {
    // Two boxes stacked, joined right-side to right-side: inferring the bow
    // from the run would send the line down out of a side it leaves sideways.
    const run = route(
      LEFT,
      BELOW,
      link("a", "b", {
        curve: "s",
        source_side: "right",
        target_side: "right",
      }),
    );

    expect(run.control![0].x).toBeGreaterThan(run.start.x);
    expect(run.control![1].x).toBeGreaterThan(run.end.x);
  });

  it("aims the head along the curve rather than along the straight line", () => {
    const run = route(
      LEFT,
      BELOW,
      link("a", "b", {
        curve: "s",
        source_side: "right",
        target_side: "right",
      }),
    );

    // Arriving from the right, so the head points left — which the straight
    // line between the two ends (pointing down) would have got wrong.
    expect(run.atEnd.x).toBeLessThan(0);
    expect(Math.hypot(run.atEnd.x, run.atEnd.y)).toBeCloseTo(1);
  });

  it("puts a label halfway along the curve, not halfway between the ends", () => {
    const straight = midpoint(route(LEFT, RIGHT, link("a", "b")));
    expect(near(straight)).toEqual({ x: 0.5, y: 0.5 });

    const bowed = midpoint(
      route(
        LEFT,
        BELOW,
        link("a", "b", {
          curve: "s",
          source_side: "right",
          target_side: "right",
        }),
      ),
    );
    expect(bowed.x).toBeGreaterThan(
      Math.max(LEFT.x + LEFT.w, BELOW.x + BELOW.w),
    );
  });
});

describe("whether a word fits on an arrow", () => {
  it("measures the run in cells, because a fraction is not a length", () => {
    // The same fraction across a wide widget and down a short one are very
    // different distances on the glass.
    expect(cells({ x: 0, y: 0 }, { x: 0.5, y: 0 }, 12, 4)).toBe(6);
    expect(cells({ x: 0, y: 0 }, { x: 0, y: 0.5 }, 12, 4)).toBe(2);
  });

  it("drops a word the arrow is too short to hold", () => {
    expect(roomy("ok", 3)).toBe(true);
    expect(roomy("ok", 0.5)).toBe(false);
  });

  it("drops a long word off an arrow a short one would have fitted", () => {
    // gantt's `roomy` can ignore the length because a bar clips its own name.
    // An arrow clips nothing, so a long word would overhang both ends.
    expect(roomy("ok", 2)).toBe(true);
    expect(roomy("needs another build", 2)).toBe(false);
  });
});
