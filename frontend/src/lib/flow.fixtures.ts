/**
 * The bench the flow tests are read on: a few graphs, a few widget shapes, and
 * the small measurements that turn an arrow back into numbers.
 *
 * Split out of `flow.test.ts` for the same reason `flow-ranks.ts` split out of
 * `flow.ts` — the file had grown past what one subject is worth, and the seam
 * was already there. Nothing here asserts anything; it only makes a fact about
 * a flow expressible in one line.
 */
import type { FlowLink, FlowNode, FlowPayload } from "@/lib/schemas/board";
import type { Box, Point, Route } from "@/lib/flow";
import { cells, layout } from "@/lib/flow";

export function node(id: string, box?: Partial<FlowNode>): FlowNode {
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

export function link(
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
export function near(at: Point) {
  return { x: Math.round(at.x * 1e4) / 1e4, y: Math.round(at.y * 1e4) / 1e4 };
}

/** The one arrow between these two, which is all a flow ever draws. */
export function only(
  drawn: { link: FlowLink; run: Route }[],
  source: string,
  target: string,
): Route {
  return drawn.find(
    (arrow) => arrow.link.source === source && arrow.link.target === target,
  )!.run;
}

/** Where an arrow is, a given fraction of the way along it. */
export function walk(run: Route, t: number): Point {
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
export function sample(run: Route): Point[] {
  return Array.from({ length: 65 }, (_, step) => walk(run, step / 64));
}

/**
 * The nearest two arrows ever come to each other, in cells — which is what
 * decides whether they read as two arrows from a sofa, rather than the distance
 * between their ends.
 */
export function apart(a: Route, b: Route, cols: number, rows: number): number {
  const closest = Math.min(
    ...sample(a).flatMap((one) =>
      sample(b).map((other) => cells(one, other, cols, rows)),
    ),
  );
  return Math.round(closest * 1e4) / 1e4;
}

export const WIDE = { cols: 12, rows: 4 };
export const TALL = { cols: 4, rows: 12 };

export function flow(nodes: FlowNode[], links: FlowLink[] = []): FlowPayload {
  return { kind: "flow", title: null, icon: null, nodes, links };
}

/** A flow laid out in a widget of the given shape. */
export function where(nodes: FlowNode[], links: FlowLink[] = [], size = WIDE) {
  return layout(flow(nodes, links), size.cols, size.rows);
}

/** Whether two boxes share any area at all. */
export function touching(a: Box, b: Box): boolean {
  return (
    a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
  );
}

/** Every pair of boxes that overlaps. Named, so a failure says which two. */
export function overlaps(placed: Map<string, Box>): string[] {
  const all = [...placed];
  return all.flatMap(([name, box], at) =>
    all
      .slice(at + 1)
      .filter(([, other]) => touching(box, other))
      .map(([other]) => `${name}/${other}`),
  );
}
/** One box, then two beside each other, then one where they join. */
export const DIAMOND = ["start", "left", "right", "join"].map((id) => node(id));
export const SPLITS = [
  link("start", "left"),
  link("start", "right"),
  link("left", "join"),
  link("right", "join"),
];

/** One box, then a branch of two, then one where they join — five in four ranks. */
export const SPLIT_JOIN = ["pull", "build", "test", "lint", "ship"].map((id) =>
  node(id),
);
export const SPLIT_JOIN_LINKS = [
  link("pull", "build"),
  link("build", "test"),
  link("build", "lint"),
  link("test", "ship"),
  link("lint", "ship"),
];

/** clone, build, test, ship — and a red test that sends you back to build. */
export const PIPELINE = ["clone", "build", "test", "ship"].map((id) =>
  node(id),
);
export const RETRY = [
  link("clone", "build"),
  link("build", "test"),
  link("test", "ship"),
  link("test", "build", { label: "red", curve: "s" }),
];
export const LEFT = { x: 0.1, y: 0.4, w: 0.2, h: 0.2 };
export const RIGHT = { x: 0.7, y: 0.4, w: 0.2, h: 0.2 };
export const BELOW = { x: 0.1, y: 0.7, w: 0.2, h: 0.2 };

// A square widget, where a fraction across and a fraction down are the same
// distance. These cases are about which side an arrow meets, not about the
// widget, and a square one is the shape that lets them say only that.
export const SQUARE = { cols: 8, rows: 8 };
