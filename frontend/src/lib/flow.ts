import type {
  FlowLink,
  FlowNode,
  FlowPayload,
  FlowSide,
} from "@/lib/schemas/board";

/**
 * Reading a flow: where each box lands, where an arrow meets it, and whether
 * an arrow is long enough to carry a word.
 *
 * All of it is a pure function of the payload and the widget's shape, and none
 * of it is stored — the same division `lib/gantt.ts` makes, for the same
 * reason. The board keeps what was said; the geometry is a reading, and this is
 * where it is taken.
 *
 * Everything here is in **fractions of the widget**: `x` and `w` of its width,
 * `y` and `h` of its height, `0` its top-left and `1` its bottom-right. That is
 * `Point` in `scorsese_core::shape` read inward, and it is why a flow means the
 * same thing in a 3x2 widget and in a 16x9 one. Two fractions of different
 * things are not comparable as lengths, which is what `cells` exists to fix.
 *
 * No React and no DOM, so the arithmetic can be tested without a browser.
 */

/** A box on the widget, in fractions of it. */
export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** A place on the widget, in fractions of it. */
export interface Point {
  x: number;
  y: number;
}

/**
 * How much of its slot a box takes along the line, when nothing said where it
 * sits. The rest is the gap the arrow is drawn in, so this is also how long
 * every arrow in a fallback layout is.
 */
export const LINE_FILL = 0.68;

/** How much of the widget's short side a box takes across the line. */
export const LINE_CROSS = 0.46;

/**
 * The shortest arrow worth putting any word on, in cells.
 *
 * A cell is roughly 60px on the television this is read from, so one and a half
 * of them is about 90px — below which a label is not small, it is a smudge
 * lying across a line. Measured in cells rather than in fractions because a
 * fraction of a 3-cell widget and a fraction of a 12-cell one are different
 * lengths, and it is the length on the glass that decides.
 */
export const LABEL_FLOOR_CELLS = 1.5;

/**
 * How many cells one character of a label needs.
 *
 * `gantt.ts` asks only whether the bar is wide enough, ignoring how long the
 * name is, and it can: a bar's name is clipped by the bar. A link label has
 * nothing to clip it, so a long word on a short arrow overhangs both ends and
 * reads as a mistake in the drawing rather than in the data. Hence the length.
 */
export const LABEL_CELLS_PER_CHAR = 0.2;

/**
 * How far an S bows out of each end, as a fraction of the run between the two
 * anchors.
 *
 * A half puts each control point the familiar connector's distance out. It is
 * not a field for the same reason the bow's axis is not one — scorsese: an
 * author drawing a diagram has an opinion about which two things are joined,
 * not about the curvature of the join.
 */
export const BOW = 0.5;

/**
 * Where every box in this flow sits.
 *
 * Either they all said — in which case this is what they said, unchanged — or
 * none did, and they are drawn in one evenly spaced line along the widget's
 * longer side. The backend refuses the mixture, so there is no third case.
 *
 * The fallback is deliberately dumb: one line, uniform boxes, evenly spaced.
 * It is enough that `add_flow` with nothing but steps and arrows produces
 * something worth looking at, and it is the seam a ranked layout plugs into —
 * everything downstream of here reads boxes and knows nothing about how they
 * were chosen.
 */
export function boxes(
  nodes: FlowNode[],
  cols: number,
  rows: number,
): Map<string, Box> {
  const placed = new Map<string, Box>();
  const along = cols >= rows ? "x" : "y";
  nodes.forEach((node, at) => {
    placed.set(node.id, said(node) ?? inLine(at, nodes.length, along));
  });
  return placed;
}

/** The box a node named, or null when it named none. */
function said(node: FlowNode): Box | null {
  if (node.x === null || node.y === null || node.w === null || node.h === null)
    return null;
  return { x: node.x, y: node.y, w: node.w, h: node.h };
}

/** One box's slot in an evenly spaced line of `count` along the long side. */
function inLine(at: number, count: number, along: "x" | "y"): Box {
  const slot = 1 / count;
  const length = slot * LINE_FILL;
  const near = slot * at + (slot - length) / 2;
  const across = (1 - LINE_CROSS) / 2;
  return along === "x"
    ? { x: near, y: across, w: length, h: LINE_CROSS }
    : { x: across, y: near, w: LINE_CROSS, h: length };
}

/**
 * Where on a box a side is, as fractions of the widget.
 *
 * A rectangle and an ellipse answer this identically, which is not a shortcut:
 * the ellipse inscribed in a box touches that box at exactly the midpoints of
 * its four sides, so the anchor is the same point for both and the shape never
 * enters the arithmetic.
 */
export function anchor(box: Box, side: FlowSide): Point {
  const middle = { x: box.x + box.w / 2, y: box.y + box.h / 2 };
  switch (side) {
    case "left":
      return { x: box.x, y: middle.y };
    case "right":
      return { x: box.x + box.w, y: middle.y };
    case "top":
      return { x: middle.x, y: box.y };
    case "bottom":
      return { x: middle.x, y: box.y + box.h };
    case "center":
      return middle;
  }
}

/**
 * The pair of sides two boxes face each other across, when the link named none.
 *
 * Whichever axis their middles are further apart on, because that is the axis
 * the eye reads the relationship along — the same rule scorsese infers an S's
 * bow axis from, kept the same here so the two never disagree about which way
 * an arrow is going.
 *
 * This is the deliberate divergence from scorsese, which makes the author
 * choose. There an attached clip moves over time, so an arrow that picked its
 * own side would rearrange itself between two renders. Nothing in a flow moves.
 */
export function facing(from: Box, to: Box): [FlowSide, FlowSide] {
  const dx = to.x + to.w / 2 - (from.x + from.w / 2);
  const dy = to.y + to.h / 2 - (from.y + from.h / 2);
  if (Math.abs(dx) >= Math.abs(dy))
    return dx >= 0 ? ["right", "left"] : ["left", "right"];
  return dy >= 0 ? ["bottom", "top"] : ["top", "bottom"];
}

/** An arrow, once its geometry has been worked out. */
export interface Route {
  start: Point;
  end: Point;
  /** The two Bézier control points, or null for a straight line. */
  control: [Point, Point] | null;
  /** Which way the line is travelling as it arrives at `end`. */
  atEnd: Point;
  /** Which way it is travelling as it leaves `start`. A head there points back. */
  atStart: Point;
}

/** Which way a side faces out of its box. `center` faces nowhere. */
function normal(side: FlowSide): Point | null {
  switch (side) {
    case "left":
      return { x: -1, y: 0 };
    case "right":
      return { x: 1, y: 0 };
    case "top":
      return { x: 0, y: -1 };
    case "bottom":
      return { x: 0, y: 1 };
    case "center":
      return null;
  }
}

/**
 * Where one arrow runs, given the boxes at its two ends.
 *
 * An S leaves each end along that end's **own outward normal** rather than
 * along the dominant axis of the run. For two boxes side by side — right out of
 * one, left into the next — that is exactly scorsese's rule and draws exactly
 * scorsese's shape. It differs only where scorsese could not be asked: two
 * stacked boxes joined right-side to right-side bow out to the right and back,
 * where inferring from the run would have sent the line down out of a side it
 * leaves horizontally, which reads as a fault in the renderer.
 *
 * A `center` end has no side to leave along, so it leaves along the run — an S
 * into the middle of a box is a straight line, honestly.
 */
export function route(from: Box, to: Box, link: FlowLink): Route {
  const [a, b] = sides(from, to, link);
  const start = anchor(from, a);
  const end = anchor(to, b);
  const straight = unit(end.x - start.x, end.y - start.y) ?? { x: 1, y: 0 };
  if (link.curve === "straight")
    return { start, end, control: null, atEnd: straight, atStart: straight };

  const reach = Math.hypot(end.x - start.x, end.y - start.y) * BOW;
  const out = normal(a) ?? straight;
  const back = normal(b) ?? { x: -straight.x, y: -straight.y };
  const control: [Point, Point] = [
    { x: start.x + out.x * reach, y: start.y + out.y * reach },
    { x: end.x + back.x * reach, y: end.y + back.y * reach },
  ];
  // A cubic's tangent at each end runs from the end to the control point beside
  // it. When the bow collapses — the control point landing on its own end —
  // that vector is zero and the straight line between the ends is the honest
  // fallback.
  return {
    start,
    end,
    control,
    atEnd: unit(end.x - control[1].x, end.y - control[1].y) ?? straight,
    atStart: unit(control[0].x - start.x, control[0].y - start.y) ?? straight,
  };
}

/** The two sides this link meets: what it named, else the facing pair. */
function sides(from: Box, to: Box, link: FlowLink): [FlowSide, FlowSide] {
  const picked = facing(from, to);
  return [link.source_side ?? picked[0], link.target_side ?? picked[1]];
}

/** A direction of length one, or null when there is no direction at all. */
function unit(dx: number, dy: number): Point | null {
  const length = Math.hypot(dx, dy);
  if (!Number.isFinite(length) || length <= 0) return null;
  return { x: dx / length, y: dy / length };
}

/**
 * How long a straight run across the widget actually is, in board cells.
 *
 * The two fractions are of different things, so they cannot be squared and
 * added as they stand: a run of 0.5 across a 12-cell widget is four times the
 * run of 0.5 down a 3-cell one. Scaling each by the widget's own extent puts
 * them in the same unit first.
 */
export function cells(
  from: Point,
  to: Point,
  cols: number,
  rows: number,
): number {
  return Math.hypot((to.x - from.x) * cols, (to.y - from.y) * rows);
}

/**
 * Whether an arrow this long can carry this word.
 *
 * The move `gantt.ts` makes with `roomy()` and `clock.tsx` with the date: a
 * word half-overlapping an arrow is worse than no word, so it comes off rather
 * than being shrunk until it is unreadable anyway.
 */
export function roomy(label: string, run: number): boolean {
  return (
    run >= Math.max(LABEL_FLOOR_CELLS, label.length * LABEL_CELLS_PER_CHAR)
  );
}

/** Where a label sits on its arrow: the midpoint, nudged off the line. */
export function midpoint(run: Route): Point {
  if (run.control === null)
    return {
      x: (run.start.x + run.end.x) / 2,
      y: (run.start.y + run.end.y) / 2,
    };
  // The point halfway along a cubic, which on a bowed arrow is nowhere near
  // halfway between its ends.
  const [a, b] = run.control;
  return {
    x: (run.start.x + 3 * a.x + 3 * b.x + run.end.x) / 8,
    y: (run.start.y + 3 * a.y + 3 * b.y + run.end.y) / 8,
  };
}

/** Every arrow in a flow, already routed, with the ones that lead nowhere gone. */
export function arrows(
  payload: FlowPayload,
  placed: Map<string, Box>,
): { link: FlowLink; run: Route }[] {
  return payload.links.flatMap((link) => {
    const from = placed.get(link.source);
    const to = placed.get(link.target);
    // The backend refuses a link naming a node that is not there, so this is
    // only ever a board file written by hand. Dropping the arrow is better than
    // drawing it from nowhere.
    if (!from || !to) return [];
    return [{ link, run: route(from, to, link) }];
  });
}
