/**
 * What a flow shows, mirroring `backend/schemas/flow.py`.
 *
 * Its own module for the reason it has one there: a payload made of two further
 * models is not one more block of fields, and `board.ts` is at the house's
 * 550-line ceiling. `board.ts` re-exports all of it, so nothing has to know.
 *
 * Every number here is a **fraction of the widget** — `x` and `w` of its width,
 * `y` and `h` of its height — so a flow means the same thing at every widget
 * size. `lib/flow.ts` is where those fractions are read.
 */

import type { IconRef } from "@/lib/schemas/board";

/**
 * Which part of a box an arrow meets. `center` points *at* a box rather than
 * touching it, so the arrow is drawn across it — which is what was asked for.
 */
export type FlowSide = "left" | "right" | "top" | "bottom" | "center";

/**
 * One box in a flow, with a word in it.
 *
 * `x`/`w` are fractions of the widget's width and `y`/`h` of its height, so the
 * drawing means the same thing at every widget size. All four or none: the
 * backend refuses half a rectangle, and refuses a flow where some boxes say
 * where they sit and others do not. When none of them say, `lib/flow.ts` draws
 * the line they are laid out in.
 *
 * `node` is the correct word here and only here — inside a flow there is a
 * graph. The `text-node-*` type scale is the older, unrelated sense of the word
 * and means *widget*.
 */
export interface FlowNode {
  id: string;
  text: string;
  shape: "rectangle" | "ellipse";
  /** A fraction of the box's own shorter side: 0 square, 0.5 a pill. */
  radius: number;
  /** Washed for the interior, full strength for the outline. Null is the ink. */
  color: string | null;
  x: number | null;
  y: number | null;
  w: number | null;
  h: number | null;
}

/**
 * An arrow from one box to another.
 *
 * `source`/`target` rather than `from`/`to` because `from` is a keyword on the
 * other side of the wire, and an alias would have reached this file as `from`
 * over HTTP and `from_` over the socket.
 */
export interface FlowLink {
  source: string;
  target: string;
  /** Null lets the widget pick the pair of facing sides. */
  source_side: FlowSide | null;
  target_side: FlowSide | null;
  /** Dropped when the arrow is too short to hold it. */
  label: string | null;
  curve: "straight" | "s";
  heads: "none" | "end" | "both";
  /** Always drawn at full strength: an arrow is a mark and marks are not washed. */
  color: string | null;
}

/**
 * A diagram of boxes and arrows, drawn whole inside one widget.
 *
 * The thing no other widget here can say: *this leads to that*. The diagram is
 * the widget and the arrow is a line inside it — a free-standing arrow joining
 * two widgets would make the board a canvas and dragging load-bearing.
 *
 * Nothing in it is interactive and nothing about it is stored computed. Where
 * an unplaced box lands is a reading `lib/flow.ts` takes on every render.
 */
export interface FlowPayload {
  kind: "flow";
  title: string | null;
  icon: IconRef | null;
  nodes: FlowNode[];
  links: FlowLink[];
}
