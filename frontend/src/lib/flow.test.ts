/**
 * Reading a flow: where the boxes land, where the arrows meet them, and when a
 * word is dropped off one.
 *
 * The widget's shape is stated rather than measured, so every one of these is a
 * fact about the arithmetic and not about a browser that is not running. What
 * cannot be checked here is how any of it looks — that is a television.
 */
import { describe, expect, it } from "vitest";
import type { FlowLink, FlowNode, FlowPayload } from "@/lib/schemas/board";
import type { Box, Point, Route } from "@/lib/flow";
import {
  anchor,
  arrows,
  cells,
  facing,
  layout,
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

/** The one arrow between these two, which is all a flow ever draws. */
function only(
  drawn: { link: FlowLink; run: Route }[],
  source: string,
  target: string,
): Route {
  return drawn.find(
    (arrow) => arrow.link.source === source && arrow.link.target === target,
  )!.run;
}

/** Where an arrow is, a given fraction of the way along it. */
function walk(run: Route, t: number): Point {
  if (run.control === null)
    return {
      x: run.start.x + (run.end.x - run.start.x) * t,
      y: run.start.y + (run.end.y - run.start.y) * t,
    };
  const [a, b] = run.control;
  const u = 1 - t;
  const cubic = (p: number, q: number, r: number, s: number) =>
    u * u * u * p + 3 * u * u * t * q + 3 * u * t * t * r + t * t * t * s;
  return {
    x: cubic(run.start.x, a.x, b.x, run.end.x),
    y: cubic(run.start.y, a.y, b.y, run.end.y),
  };
}

/** An arrow, as points along it. Enough of them to find its nearest approach. */
function sample(run: Route): Point[] {
  return Array.from({ length: 65 }, (_, step) => walk(run, step / 64));
}

/**
 * The nearest two arrows ever come to each other, in cells — which is what
 * decides whether they read as two arrows from a sofa, rather than the distance
 * between their ends.
 */
function apart(a: Route, b: Route, cols: number, rows: number): number {
  const closest = Math.min(
    ...sample(a).flatMap((one) =>
      sample(b).map((other) => cells(one, other, cols, rows)),
    ),
  );
  return Math.round(closest * 1e4) / 1e4;
}

const WIDE = { cols: 12, rows: 4 };
const TALL = { cols: 4, rows: 12 };

function flow(nodes: FlowNode[], links: FlowLink[] = []): FlowPayload {
  return { kind: "flow", title: null, icon: null, nodes, links };
}

/** A flow laid out in a widget of the given shape. */
function where(nodes: FlowNode[], links: FlowLink[] = [], size = WIDE) {
  return layout(flow(nodes, links), size.cols, size.rows);
}

/** Whether two boxes share any area at all. */
function touching(a: Box, b: Box): boolean {
  return (
    a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
  );
}

/** Every pair of boxes that overlaps. Named, so a failure says which two. */
function overlaps(placed: Map<string, Box>): string[] {
  const all = [...placed];
  return all.flatMap(([name, box], at) =>
    all
      .slice(at + 1)
      .filter(([, other]) => touching(box, other))
      .map(([other]) => `${name}/${other}`),
  );
}

describe("where the boxes land", () => {
  it("puts a node exactly where it said it sits", () => {
    const laid = where([node("build", { x: 0.1, y: 0.2, w: 0.3, h: 0.4 })]);

    expect(laid.boxes.get("build")).toEqual({ x: 0.1, y: 0.2, w: 0.3, h: 0.4 });
  });

  it("lays a flow with no arrows in it out along the widget's longer side", () => {
    // Nothing leads to anything, so there is no graph to rank: the boxes are
    // just boxes, and they take the long side.
    const laid = where([node("a"), node("b"), node("c")]);
    const along = ["a", "b", "c"].map((id) => laid.boxes.get(id)!);

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
    const laid = where([node("a"), node("b")], [], TALL);
    const down = ["a", "b"].map((id) => laid.boxes.get(id)!);

    expect(down.map((box) => box.h)).toEqual([LINE_FILL / 2, LINE_FILL / 2]);
    expect(down[0].y).toBeLessThan(down[1].y);
    expect(down[0].x).toBe(down[1].x);
  });

  it("keeps every box it lays out inside the widget", () => {
    for (const count of [1, 2, 5, 9]) {
      const nodes = Array.from({ length: count }, (_, at) => node(`n${at}`));
      for (const box of where(nodes).boxes.values()) {
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.y).toBeGreaterThanOrEqual(0);
        expect(box.x + box.w).toBeLessThanOrEqual(1);
        expect(box.y + box.h).toBeLessThanOrEqual(1);
      }
    }
  });
});

/** One box, then two beside each other, then one where they join. */
const DIAMOND = ["start", "left", "right", "join"].map((id) => node(id));
const SPLITS = [
  link("start", "left"),
  link("start", "right"),
  link("left", "join"),
  link("right", "join"),
];

/** clone, build, test, ship — and a red test that sends you back to build. */
const PIPELINE = ["clone", "build", "test", "ship"].map((id) => node(id));
const RETRY = [
  link("clone", "build"),
  link("build", "test"),
  link("test", "ship"),
  link("test", "build", { label: "red", curve: "s" }),
];

describe("ranks", () => {
  it("puts a node one rank past the deepest thing leading into it", () => {
    // `start` leads to both, and `left` leads to `right` as well: the long path
    // decides, so `right` sits after `left` rather than beside it.
    const laid = where(
      [node("start"), node("right"), node("left")],
      [link("start", "left"), link("start", "right"), link("left", "right")],
    );

    expect([...laid.ranks]).toEqual([
      ["start", 0],
      ["right", 2],
      ["left", 1],
    ]);
  });

  it("draws a branch as one box, then two side by side, then one", () => {
    const laid = where(DIAMOND, SPLITS);
    const box = (id: string) => laid.boxes.get(id)!;

    // Along the flow: three ranks, in order.
    expect(box("start").x).toBeLessThan(box("left").x);
    expect(box("left").x).toBe(box("right").x);
    expect(box("left").x).toBeLessThan(box("join").x);
    // Across it: the two middle boxes are apart, and the single ones centred.
    expect(box("left").y).toBeLessThan(box("right").y);
    expect(box("start").y).toBe(box("join").y);
  });

  it("gives every box in the flow one size, whatever its rank holds", () => {
    const sizes = new Set(
      [...where(DIAMOND, SPLITS).boxes.values()].map(
        (box) => `${box.w}x${box.h}`,
      ),
    );

    expect(sizes.size).toBe(1);
  });

  it("overlaps nothing, on a branch or on a merge", () => {
    const merge = [link("start", "join"), link("left", "join")];

    expect(overlaps(where(DIAMOND, SPLITS).boxes)).toEqual([]);
    expect(overlaps(where(DIAMOND, merge).boxes)).toEqual([]);
    expect(overlaps(where(DIAMOND, SPLITS, TALL).boxes)).toEqual([]);
  });

  it("keeps every ranked box inside the widget", () => {
    for (const size of [WIDE, TALL]) {
      for (const box of where(DIAMOND, SPLITS, size).boxes.values()) {
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.y).toBeGreaterThanOrEqual(0);
        expect(box.x + box.w).toBeLessThanOrEqual(1);
        expect(box.y + box.h).toBeLessThanOrEqual(1);
      }
    }
  });

  it("draws a chain in exactly the line a chain was always drawn in", () => {
    // A flow that is a line has one node per rank, so the ranked layout has to
    // agree to the last digit with the line #77 drew. It is the same arithmetic.
    const chain = [node("a"), node("b"), node("c")];

    expect(where(chain, [link("a", "b"), link("b", "c")]).boxes).toEqual(
      where(chain).boxes,
    );
  });

  it("ranks a cycle without hanging, and keeps every link", () => {
    const round = [node("a"), node("b"), node("c")];
    const links = [link("a", "b"), link("b", "c"), link("c", "a")];
    const laid = where(round, links);

    // `c -> a` is the link that closes the loop, so it is the one left out of
    // the layering — depth-first from the payload's first node.
    expect([...laid.ranks.values()]).toEqual([0, 1, 2]);
    expect(arrows(flow(round, links), laid)).toHaveLength(3);
    expect(overlaps(laid.boxes)).toEqual([]);
  });

  it("gives the same geometry for the same payload, every time", () => {
    const payload = flow(PIPELINE, RETRY);
    const once = layout(payload, TALL.cols, TALL.rows);
    const again = layout(payload, TALL.cols, TALL.rows);

    expect(again.boxes).toEqual(once.boxes);
    expect(again.ranks).toEqual(once.ranks);
    expect(arrows(payload, again)).toEqual(arrows(payload, once));
  });
});

describe("the way back", () => {
  it("does not draw the loop down the corridor the forward arrow uses", () => {
    // What the television showed: in a tall widget the back-link took the same
    // two anchors as the arrow it returns along, and the two read as one
    // double-headed arrow rather than as a loop.
    const payload = flow(PIPELINE, RETRY);
    const drawn = arrows(payload, layout(payload, TALL.cols, TALL.rows));
    const forward = only(drawn, "build", "test");
    const back = only(drawn, "test", "build");

    expect(near(back.start)).not.toEqual(near(forward.end));
    // Nearly a cell and a half apart at their closest, which on this television
    // is some 80px — two arrows, not one arrow with two heads.
    expect(apart(forward, back, TALL.cols, TALL.rows)).toBeCloseTo(1.3736, 4);
  });

  it("bows out past the side of the diagram, and stays in the widget", () => {
    const payload = flow(PIPELINE, RETRY);
    const laid = layout(payload, TALL.cols, TALL.rows);
    const back = only(arrows(payload, laid), "test", "build");
    const edge = laid.boxes.get("test")!;

    // Out of the right face, back in at the right face, and every point of it
    // clear of the boxes and inside the widget.
    expect(back.start.x).toBe(edge.x + edge.w);
    expect(back.end.x).toBe(edge.x + edge.w);
    expect(back.atEnd).toEqual({ x: -1, y: 0 });
    for (const point of sample(back)) {
      expect(point.x).toBeGreaterThanOrEqual(edge.x + edge.w);
      expect(point.x).toBeLessThanOrEqual(1);
    }
  });

  it("loops beneath a flow that runs rightwards, where no title is", () => {
    const payload = flow(PIPELINE, RETRY);
    const laid = layout(payload, WIDE.cols, WIDE.rows);
    const back = only(arrows(payload, laid), "test", "build");
    const edge = laid.boxes.get("test")!;

    expect(back.start.y).toBe(edge.y + edge.h);
    expect(back.atEnd).toEqual({ x: 0, y: -1 });
  });

  it("leaves a flow that placed its own boxes exactly as it was written", () => {
    // The whole of this issue is about flows that said nothing. One that said
    // where its boxes sit is drawn there, and its arrows are routed the way #77
    // routed them — including a back-link laid over its own forward arrow,
    // which in a placed flow is the author's own drawing.
    const nodes = [
      node("a", { x: 0.1, y: 0.2, w: 0.3, h: 0.4 }),
      node("b", { x: 0.6, y: 0.2, w: 0.3, h: 0.4 }),
    ];
    const links = [link("a", "b"), link("b", "a")];
    const laid = where(nodes, links);

    expect(laid.boxes.get("a")).toEqual({ x: 0.1, y: 0.2, w: 0.3, h: 0.4 });
    expect(laid.boxes.get("b")).toEqual({ x: 0.6, y: 0.2, w: 0.3, h: 0.4 });
    expect(laid.ranks.size).toBe(0);
    const [there, back] = arrows(flow(nodes, links), laid);
    expect(near(there.run.start)).toEqual({ x: 0.4, y: 0.4 });
    expect(near(there.run.end)).toEqual({ x: 0.6, y: 0.4 });
    expect(near(back.run.start)).toEqual({ x: 0.6, y: 0.4 });
    expect(near(back.run.end)).toEqual({ x: 0.4, y: 0.4 });
    expect(back.run.control).toBeNull();
  });

  it("leaves a back-link that named its own sides where it said", () => {
    const payload = flow(PIPELINE, [
      ...RETRY.slice(0, 3),
      link("test", "build", { source_side: "left", target_side: "left" }),
    ]);
    const laid = layout(payload, TALL.cols, TALL.rows);
    const back = only(arrows(payload, laid), "test", "build");

    expect(back.start.x).toBe(laid.boxes.get("test")!.x);
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
