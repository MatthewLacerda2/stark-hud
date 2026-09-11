import { layer } from "@/lib/flow-ranks";
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
 * How much of its slot a box takes along the flow, when nothing said where it
 * sits. The rest is the gap the arrow is drawn in, so this is also how long
 * every arrow between two neighbouring ranks is.
 */
export const LINE_FILL = 0.68;

/**
 * How much of the widget a box takes across the flow, shared out between the
 * boxes of the widest rank. One rank of one box takes this much of the short
 * side; a rank of three takes a third of it each.
 */
export const LINE_CROSS = 0.46;

/**
 * How far out of the diagram the way back bows, as a share of the room left
 * between the boxes and the widget's edge.
 *
 * A share rather than a fixed distance because the room is all there is: a flow
 * is clipped and never scrolled, so a bow that left the widget would simply be
 * cut off. Eight tenths of it puts the arrow clearly outside the column of boxes
 * with the last fifth still to spare.
 */
export const LOOP_REACH = 0.8;

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
 * Which way a flow runs.
 *
 * Along the widget's longer side, so a diagram never reads downwards in a widget
 * that is wide. **Inferred from the widget, not named in the payload** — the
 * same call the board already makes about placement: omit `x` and `y` and the
 * placer chooses. A `direction` field would be one more thing for a session that
 * cannot see the television to get wrong, and a flow in a 6x3 widget that
 * insisted on running downwards is a flow nobody can read.
 */
export type Axis = "x" | "y";

/** Where every box in a flow landed, and what the reading knows about it. */
export interface Layout {
  /** Where each box sits, by node id. */
  boxes: Map<string, Box>;
  /**
   * How far down the graph each node sits. Empty when the nodes said where they
   * sit: nothing was layered then, and nothing about such a flow is
   * second-guessed.
   */
  ranks: Map<string, number>;
  /** Which way this flow runs. */
  along: Axis;
  /**
   * How many board cells the widget spans, kept from the call that laid this
   * out.
   *
   * An arrow needs them: `x` is a fraction of the width and `y` a fraction of
   * the height, so the two are not comparable until each is multiplied by its
   * own extent. Carried here rather than passed again beside the layout,
   * because a layout drawn against a different widget than it was laid out in
   * is not a thing that should be expressible.
   */
  cols: number;
  rows: number;
}

/**
 * Where every box in this flow sits.
 *
 * Three readings, in the order they are asked:
 *
 * 1. **Every node said.** Then this is what they said, unchanged — no ranks, no
 *    rerouting, nothing. The backend refuses the mixture, so one node answering
 *    settles it for all of them.
 * 2. **Nothing leads to anything.** There is no graph to rank, so the boxes take
 *    one evenly spaced line along the widget's longer side.
 * 3. **Otherwise, ranks.** Longest-path layering: a node sits one past the
 *    deepest of its sources, and a node nothing leads to starts at zero. Every
 *    node in a rank sits the same distance along the flow, spread evenly across
 *    it. That is the shape a flowchart already has in everyone's head, it is
 *    deterministic, and unlike a force simulation it produces a picture whose
 *    shape means something from a sofa.
 *
 * Nothing computed here is ever stored: `board.hud` holds what was said, the
 * same division `GanttPayload` makes about its own window. Re-tuning this later
 * does not mean rewriting every board that was ever written.
 */
export function layout(
  payload: FlowPayload,
  cols: number,
  rows: number,
): Layout {
  const along: Axis = cols >= rows ? "x" : "y";
  const nodes = payload.nodes;
  const given = nodes.map(said);
  if (given.every((box) => box !== null))
    return {
      boxes: new Map(
        nodes.map((node, at): [string, Box] => [node.id, given[at]!]),
      ),
      ranks: new Map(),
      along,
      cols,
      rows,
    };
  if (payload.links.length === 0)
    return { boxes: inLine(nodes, along), ranks: new Map(), along, cols, rows };
  const ranks = layer(payload);
  return { boxes: spread(nodes, ranks, along), ranks, along, cols, rows };
}

/** The box a node named, or null when it named none. */
function said(node: FlowNode): Box | null {
  if (node.x === null || node.y === null || node.w === null || node.h === null)
    return null;
  return { x: node.x, y: node.y, w: node.w, h: node.h };
}

/** Boxes in one evenly spaced line along the widget's longer side. */
function inLine(nodes: FlowNode[], along: Axis): Map<string, Box> {
  const slot = 1 / nodes.length;
  const length = slot * LINE_FILL;
  const across = (1 - LINE_CROSS) / 2;
  return new Map(
    nodes.map((node, at): [string, Box] => {
      const near = slot * at + (slot - length) / 2;
      return [
        node.id,
        along === "x"
          ? { x: near, y: across, w: length, h: LINE_CROSS }
          : { x: across, y: near, w: LINE_CROSS, h: length },
      ];
    }),
  );
}

/**
 * Boxes in ranks: each rank the same distance along the flow, its nodes spread
 * evenly across it.
 *
 * **One size for every box in the flow**, from the rank counts and nothing else
 * — not from how long each word is, which draws a row of differently sized boxes
 * whose differences mean nothing. The deepest rank decides the length along the
 * flow; the widest decides the width across it.
 *
 * Nothing can overlap, and not by luck: a rank's boxes are strictly shorter than
 * their own rank's slot along the flow, and every box is strictly narrower than
 * its own place across it, because both `LINE_FILL` and `LINE_CROSS` are below
 * one and the widest rank sets the width for all of them.
 */
function spread(
  nodes: FlowNode[],
  rank: Map<string, number>,
  along: Axis,
): Map<string, Box> {
  // Ranks run 0, 1, 2... with no gaps: a node at rank r above zero has a source
  // at r - 1, by construction.
  const deep = Math.max(...rank.values()) + 1;
  const files: FlowNode[][] = Array.from({ length: deep }, () => []);
  for (const node of nodes) files[rank.get(node.id) ?? 0].push(node);
  const broad = Math.max(...files.map((file) => file.length));
  const long = LINE_FILL / deep;
  const wide = LINE_CROSS / broad;
  const placed = new Map<string, Box>();
  files.forEach((file, at) => {
    const near = at / deep + (1 / deep - long) / 2;
    const slot = 1 / file.length;
    file.forEach((node, seat) => {
      const across = slot * seat + (slot - wide) / 2;
      placed.set(
        node.id,
        along === "x"
          ? { x: near, y: across, w: long, h: wide }
          : { x: across, y: near, w: wide, h: long },
      );
    });
  });
  return placed;
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
 * Whichever axis their middles are further apart on **as they are drawn**,
 * because that is the axis the eye reads the relationship along — the same rule
 * scorsese infers an S's bow axis from, kept the same here so the two never
 * disagree about which way an arrow is going.
 *
 * "As they are drawn" is the whole of it, and is why the widget's size has to
 * come in. `x` is a fraction of the width and `y` a fraction of the height, so
 * the two are fractions of different things and comparing them as they stand
 * asks whether 0.3 of one length beats 0.25 of another — a question with no
 * answer. In a tall widget that reads every vertical gap as smaller than it is,
 * so a box directly above another was joined side to side, and the arrow came
 * out of a face nothing was on and grazed past the box it was pointing at.
 * Multiplying each by its own extent puts them in board cells first, which is
 * the same conversion `cells()` makes for the length of a run.
 *
 * This is the deliberate divergence from scorsese, which makes the author
 * choose. There an attached clip moves over time, so an arrow that picked its
 * own side would rearrange itself between two renders. Nothing in a flow moves.
 */
export function facing(
  from: Box,
  to: Box,
  cols: number,
  rows: number,
): [FlowSide, FlowSide] {
  const dx = (to.x + to.w / 2 - (from.x + from.w / 2)) * cols;
  const dy = (to.y + to.h / 2 - (from.y + from.h / 2)) * rows;
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
export function route(
  from: Box,
  to: Box,
  link: FlowLink,
  cols: number,
  rows: number,
): Route {
  const [a, b] = sides(from, to, link, cols, rows);
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
function sides(
  from: Box,
  to: Box,
  link: FlowLink,
  cols: number,
  rows: number,
): [FlowSide, FlowSide] {
  const picked = facing(from, to, cols, rows);
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

/**
 * Whether this link is the way back: it arrives in a rank no deeper than the one
 * it leaves, which only a link the layering had to cut can do.
 *
 * Never true of a flow that placed its own boxes — such a flow has no ranks and
 * is drawn exactly as it was written — and never true of a link that named its
 * own sides, which is an author saying where the arrow goes.
 */
function returns(link: FlowLink, laid: Layout): boolean {
  if (link.source_side !== null || link.target_side !== null) return false;
  const leaves = laid.ranks.get(link.source);
  const arrives = laid.ranks.get(link.target);
  return leaves !== undefined && arrives !== undefined && arrives <= leaves;
}

/**
 * The way back: out of the side of one box, around the outside of the diagram,
 * and in at the side of the other.
 *
 * Left to `route`, a back-link between two neighbouring ranks picks the same
 * pair of facing sides the forward arrow picked — the same two anchors, the same
 * corridor, one line laid exactly over the other. On a television that does not
 * read as a loop, it reads as a single arrow with a head at each end, which is a
 * different statement altogether. So the way back leaves the *cross* face
 * instead and bows out past it: one arrow travelling back up the outside of the
 * diagram, which is what a loop looks like when a person draws one.
 *
 * Which face is the cross face falls out of the flow's direction, and both
 * answers keep the arrow clear of a title: a flow running rightwards loops
 * beneath itself, one running downwards loops to its right.
 */
function aside(from: Box, to: Box, along: Axis): Route {
  const side: FlowSide = along === "x" ? "bottom" : "right";
  const out: Point = along === "x" ? { x: 0, y: 1 } : { x: 1, y: 0 };
  const home: Point = along === "x" ? { x: 0, y: -1 } : { x: -1, y: 0 };
  const start = anchor(from, side);
  const end = anchor(to, side);
  // How far out it bows: a share of the room left between the outermost of its
  // two ends and the widget's edge, so the channel clears the boxes without ever
  // leaving the widget — which is clipped, not scrolled.
  const edge =
    along === "x" ? Math.max(start.y, end.y) : Math.max(start.x, end.x);
  const reach = (1 - edge) * LOOP_REACH;
  const control: [Point, Point] = [
    { x: start.x + out.x * reach, y: start.y + out.y * reach },
    { x: end.x + out.x * reach, y: end.y + out.y * reach },
  ];
  // Both control points sit out on the same side, so the line leaves outwards
  // and arrives pointing back inwards at the far box's matching face. Those two
  // directions are exactly the normal and its reverse; there is nothing to
  // measure.
  return { start, end, control, atEnd: home, atStart: out };
}

/** Every arrow in a flow, already routed, with the ones that lead nowhere gone. */
export function arrows(
  payload: FlowPayload,
  laid: Layout,
): { link: FlowLink; run: Route }[] {
  return payload.links.flatMap((link) => {
    const from = laid.boxes.get(link.source);
    const to = laid.boxes.get(link.target);
    // The backend refuses a link naming a node that is not there, so this is
    // only ever a board file written by hand. Dropping the arrow is better than
    // drawing it from nowhere.
    if (!from || !to) return [];
    const run = returns(link, laid)
      ? aside(from, to, laid.along)
      : route(from, to, link, laid.cols, laid.rows);
    return [{ link, run }];
  });
}
