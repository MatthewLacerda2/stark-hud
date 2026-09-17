import type { CSSProperties } from "react";
import type { DialGroup } from "@/lib/dials";
import { DIRT } from "@/lib/dirt";

/**
 * How much the board behaves like a thing in the room rather than a picture on
 * the glass, part by part.
 *
 * A flat board tilted is a sheet of paper tilting. What reads as depth is parts
 * moving by different amounts, so the look has a subject and a camera: every
 * widget becomes a pane of glass with a thickness (`glass`), and the board as a
 * whole leans — away from the pointer (`tilt`), and slowly on its own (`sway`).
 * The background video is not part of it and stays put, which is the strongest
 * depth cue on the screen: the panes slide over the room behind them.
 *
 * On by default, at the board owner's numbers — see `SETTLED`. `?depth=0` turns
 * it off, and any part can be named on its own: `?sway=1` lets the board drift,
 * `?tilt=0` holds it still under a mouse. A named part is still scaled by
 * `depth`, so zero really is off.
 */
export type Depth = {
  /** How far the pointer pushes the board back, as if pressing into it. */
  tilt: number;
  /** How far the board drifts with nobody touching it. */
  sway: number;
  /** How present each widget's pane is: its face, its walls, its dirt. */
  glass: number;
};

/** The board exactly as it was before any of this existed. */
const FLAT: Depth = { tilt: 0, sway: 0, glass: 0 };

/**
 * Each part's default, before the master scales it.
 *
 * Settled at the television by the board owner. At full the panes were too
 * present and the lean too strong, so the master came down to half; the tilt
 * came down further, to a nudge; and sway is off, so a board nobody touches
 * holds still. Sway stays in as a dial rather than being removed — it is one
 * number away from being judged again.
 */
const SETTLED: Depth = { tilt: 0.2, sway: 0, glass: 1 };

/** How much of all of it, when the URL does not say. */
const MASTER = 0.5;

const PARTS = Object.keys(SETTLED) as (keyof Depth)[];

/**
 * The most the pointer tips the board, in degrees.
 *
 * Enough that a pointer in a corner visibly opens the side walls of every pane,
 * and short of the point where the far edge of the board shrinks enough to read
 * as the television being at an angle.
 */
const TILT_DEGREES = 5;

/**
 * The most the board drifts on its own, in degrees.
 *
 * Small on purpose. Motion on a board nobody is touching reads as a fault in the
 * screen the moment it is noticed as motion, so this is sized to be noticed as
 * depth instead: the walls breathe, and nothing appears to move.
 */
const SWAY_DEGREES = 1.2;

/**
 * The drift, as a few slow waves per axis: period in seconds, phase, weight.
 *
 * Not a random walk. A random walk has nothing pulling it home, so it wanders
 * off and has to be clamped, and a clamp looks like hitting a wall. Waves are
 * bounded by construction, and periods that share no factor keep the sum from
 * ever visibly repeating.
 */
type Wave = readonly [period: number, phase: number, weight: number];

const WAVES: Record<"x" | "y", readonly Wave[]> = {
  x: [
    [37, 0, 0.6],
    [23, 1.3, 0.4],
  ],
  y: [
    [29, 0.7, 0.6],
    [41, 2.1, 0.4],
  ],
};

function amount(raw: string | null, fallback: number): number {
  const value = raw === null ? fallback : Number(raw);
  return Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : fallback;
}

/** Read the depth out of a query string. See `Depth` for the dials. */
export function depthFrom(search: string): Depth {
  const asked = new URLSearchParams(search);
  const master = amount(asked.get("depth"), MASTER);
  const depth = { ...FLAT };
  for (const part of PARTS) {
    depth[part] = amount(asked.get(part), SETTLED[part]) * master;
  }
  return depth;
}

/** Whether any of it is on. Off, the board renders exactly as it did before. */
export function deep(depth: Depth): boolean {
  return PARTS.some((part) => depth[part] > 0);
}

/** Whether anything moves, and so whether there is a loop to run at all. */
export function moving(depth: Depth): boolean {
  return depth.tilt > 0 || depth.sway > 0;
}

/** The variables the panes read. */
export function depthVars(depth: Depth): CSSProperties {
  return {
    "--glass": depth.glass,
    "--glass-dirt": `url("${DIRT}")`,
  } as CSSProperties;
}

/** Where the pointer is, from -1 at the left or top to 1 at the right or bottom. */
export type Pointer = { x: number; y: number };

/** How far the board is turned about each axis, in degrees. */
export type Lean = { x: number; y: number };

function drift(waves: readonly Wave[], seconds: number): number {
  return waves.reduce(
    (sum, [period, phase, weight]) =>
      sum + weight * Math.sin((seconds / period) * 2 * Math.PI + phase),
    0,
  );
}

/**
 * How the board leans, given where the pointer is and how long it has existed.
 *
 * The pointer pushes rather than pulls: the side it is over goes away from the
 * viewer. A pointer to the right turns the board about its upright axis so the
 * right edge recedes, and a pointer near the top tips the top edge back.
 */
export function lean(depth: Depth, pointer: Pointer, seconds: number): Lean {
  return {
    x:
      -pointer.y * depth.tilt * TILT_DEGREES +
      drift(WAVES.x, seconds) * depth.sway * SWAY_DEGREES,
    y:
      pointer.x * depth.tilt * TILT_DEGREES +
      drift(WAVES.y, seconds) * depth.sway * SWAY_DEGREES,
  };
}

/**
 * How far to push the board away so its nearest corner stays on the screen.
 *
 * A board turned about its middle brings one side towards the camera, and under
 * perspective the near side grows. The board fills the screen edge to edge, so
 * anything that grows goes off it — widgets against the wall were cut in half.
 * Pushing the whole board back by exactly as far as the near corner came forward
 * keeps that corner where it was, and lets the far side do all of the shrinking.
 * Level, it is zero, and the board is the board.
 */
export function recede(turned: Lean, width: number, height: number): number {
  const radians = Math.PI / 180;
  return (
    Math.abs(Math.sin(turned.x * radians)) * (height / 2) +
    Math.abs(Math.sin(turned.y * radians)) * (width / 2)
  );
}

/** Depth's numbers, for the menu that turns them. */
export const DEPTH_DIALS: DialGroup = {
  name: "depth",
  master: { param: "depth", fallback: MASTER, ceiling: 1 },
  parts: PARTS.map((part) => ({
    param: part,
    fallback: SETTLED[part],
    ceiling: 1,
  })),
};
