/**
 * Turning a model into lines on a screen: the arithmetic, with no canvas in it.
 *
 * This is the whole of the 3D. There is no engine behind it because there is no
 * engine's worth of work to do — a wireframe has no lighting, no materials and
 * no surfaces, so what is left is rotating points, dividing by how far away they
 * are, and drawing a line between pairs of them. That is a page of arithmetic,
 * and a page of arithmetic that can be tested is worth more than six hundred
 * kilobytes that cannot.
 *
 * Everything here is pure and frame-independent: given an angle it says where
 * the points are, and it never asks what time it is. The component next door
 * owns the clock and the canvas.
 */
import type { MeshPart } from "@/lib/schemas/board";

/**
 * How far the camera sits from the middle of the model, in model widths.
 *
 * This is the only thing setting how much perspective there is, and it is a
 * real choice rather than a constant nobody looked at. Close in, the near face
 * of a cube swells and the model reads as a fisheye; far out, the projection
 * flattens until a spinning object looks like a turning drawing of one. Four
 * widths is about where the near edge is a third bigger than the far one, which
 * is enough for the eye to get the depth without noticing the lens.
 */
export const FOV = 4;

/** How much of the widget's shorter side the model spans at its widest. */
export const FIT = 0.86;

/**
 * How bright the far side of the model is against the near side.
 *
 * The one thing that makes a wireframe readable. Every edge is drawn — nothing
 * is hidden behind anything, because there are no surfaces to hide behind — so
 * without depth the front and the back of an object are the same tangle of
 * lines and the eye cannot tell which way it is turning. Dimming the far side
 * is what separates them, and it is also most of what makes the thing read as
 * *projected* rather than drawn.
 */
export const DEPTH_FADE = 0.28;

/**
 * How many depths the edges are sorted into before being drawn.
 *
 * A stroke per edge would be the exact thing — every line at its own
 * brightness — and it is also a canvas state change per edge, which on a
 * television is the difference between a widget that costs nothing and the most
 * expensive thing on the board. Sorting into a handful of bands and drawing each
 * band as one path costs six strokes instead of six hundred. The banding is
 * invisible: the steps are small, and they fall on a gradient rather than on an
 * edge of the object.
 */
export const BANDS = 6;

/** A point, and a part's centre. */
export type Vec3 = [number, number, number];

/** Everything about the view that does not change while one frame is drawn. */
export type Camera = {
  /** Cosine and sine of the turn about the upright axis. */
  cos: number;
  sin: number;
  /** Cosine and sine of the lean toward the camera. */
  lean: number;
  rise: number;
  /** Model units to pixels. */
  scale: number;
  /** The middle of the widget, in pixels. */
  cx: number;
  cy: number;
  /** The furthest any point gets from the middle, for normalising depth. */
  reach: number;
};

/** Where one point lands: pixels, and how near the viewer it ended up. */
export type Projected = { sx: number; sy: number; depth: number };

/**
 * How far the outermost part travels at an `explode` of 1, against the model's
 * own radius.
 *
 * Measured against the model rather than fixed, because an exploded view has to
 * fit in the same widget the assembled one did: pulling the parts apart makes
 * the thing bigger, and everything then has to be drawn smaller to fit. Spread
 * them by a whole model width and the reactor draws at a third of its size —
 * the parts separate beautifully and none of them can be made out, which is an
 * exploded diagram that has lost the thing it was explaining. Two thirds of the
 * radius is about where the parts are clearly apart and each is still legible.
 */
export const SPREAD = 0.6;

/**
 * Where each part sits and how far the model reaches, once it is pulled apart.
 *
 * The two together because neither is any use alone: the offsets are scaled
 * against the assembled model's radius, and the radius that matters for drawing
 * is the one *after* the offsets have been applied. Splitting them into two
 * exported functions would mean every caller had to know to call them in the
 * right order with the right intermediate, which is a rule to get wrong rather
 * than an interface.
 *
 * Each part travels straight out along the line from the middle of the model to
 * the middle of that part, which is what an exploded diagram has always done:
 * things come apart the way they went together.
 *
 * Two parts with the same centre never separate, and no arithmetic here can fix
 * that: concentric rings genuinely share a middle, so the direction "away from
 * the middle" is the same direction for both. That is a property of the model,
 * and the answer is to give them different depths when modelling.
 */
export function layout(
  parts: MeshPart[],
  explode: number,
): { moved: Vec3[]; reach: number } {
  const still: Vec3[] = parts.map(() => [0, 0, 0]);
  const assembled = reachOf(parts, still);
  const furthest = Math.max(
    ...parts.map((part) => Math.hypot(...part.center)),
    0,
  );
  if (explode <= 0 || furthest <= 0 || assembled <= 0)
    return { moved: still, reach: assembled };

  const step = (explode * SPREAD * assembled) / furthest;
  const moved = parts.map(
    (part) =>
      [
        part.center[0] * step,
        part.center[1] * step,
        part.center[2] * step,
      ] as Vec3,
  );
  return { moved, reach: reachOf(parts, moved) };
}

/**
 * The furthest any point of the model gets from the origin once it has moved.
 *
 * An upper bound rather than the exact figure: a part's own radius plus how far
 * its centre has travelled. The exact answer would need every vertex measured
 * against every offset, and the only thing this number does is decide how much
 * to shrink the model so it fits — so the cost of being slightly generous is a
 * slightly smaller drawing, and the cost of being exact is nothing gained.
 *
 * It must not depend on the angle. A reach that changed as the model turned
 * would rescale it every frame, and the model would breathe.
 */
export function reachOf(parts: MeshPart[], moved: Vec3[]): number {
  let worst = 0;
  parts.forEach((part, at) => {
    let radius = 0;
    for (let i = 0; i < part.verts.length; i += 3) {
      const r = Math.hypot(part.verts[i], part.verts[i + 1], part.verts[i + 2]);
      if (r > radius) radius = r;
    }
    const out = radius + Math.hypot(...moved[at]);
    if (out > worst) worst = out;
  });
  return worst;
}

/**
 * The view for one frame: where the model is pointing, and how big it draws.
 *
 * The scale solves for the near side rather than the middle. Perspective makes
 * the half of the model closest to the camera bigger than life, so fitting the
 * model's radius into the widget would let the near face spill over the edge —
 * which on a board where nothing may overlap is a wireframe drawn on top of the
 * widget next door.
 */
export function camera(
  angle: number,
  tiltDegrees: number,
  width: number,
  height: number,
  reach: number,
): Camera {
  const tilt = (tiltDegrees * Math.PI) / 180;
  // Guarded because a model the size of the camera distance would divide by
  // nothing and draw at infinity. Nothing normalised gets near it, but a reach
  // of zero — a model that is one point — is reachable by a bad file.
  const safe = Math.min(Math.max(reach, 1e-6), FOV * 0.6);
  const nearest = FOV / (FOV - safe);
  return {
    cos: Math.cos(angle),
    sin: Math.sin(angle),
    lean: Math.cos(tilt),
    rise: Math.sin(tilt),
    scale: ((Math.min(width, height) / 2) * FIT) / (safe * nearest),
    cx: width / 2,
    cy: height / 2,
    reach: safe,
  };
}

/**
 * One point, from the model's space to the widget's.
 *
 * Turn about the upright axis, lean toward the camera, divide by distance. The
 * screen's y counts downward and the model's counts up, which is the one minus
 * sign in here and the reason a model that renders upside down is almost always
 * this line.
 */
export function project(
  x: number,
  y: number,
  z: number,
  cam: Camera,
): Projected {
  const rx = x * cam.cos + z * cam.sin;
  const spun = z * cam.cos - x * cam.sin;
  const ry = y * cam.lean - spun * cam.rise;
  const depth = y * cam.rise + spun * cam.lean;
  const k = FOV / (FOV - depth);
  return {
    sx: cam.cx + rx * k * cam.scale,
    sy: cam.cy - ry * k * cam.scale,
    depth,
  };
}

/** Where a depth falls between the back of the model (0) and the front (1). */
export function depthAt(depth: number, reach: number): number {
  if (reach <= 0) return 1;
  return Math.min(Math.max((depth + reach) / (2 * reach), 0), 1);
}

/** How bright an edge at this depth is drawn, from `DEPTH_FADE` to 1. */
export function fadeAt(depth: number, reach: number): number {
  return DEPTH_FADE + (1 - DEPTH_FADE) * depthAt(depth, reach);
}

/** Which of the `BANDS` paths an edge at this depth is drawn in. */
export function bandAt(depth: number, reach: number): number {
  return Math.min(Math.floor(depthAt(depth, reach) * BANDS), BANDS - 1);
}

/** The brightness a whole band is stroked at: the middle of what it holds. */
export function bandFade(band: number): number {
  return DEPTH_FADE + ((1 - DEPTH_FADE) * (band + 0.5)) / BANDS;
}
