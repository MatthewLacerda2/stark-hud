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

/**
 * How much of the widget the model spans at its widest.
 *
 * A real margin now rather than a fudge factor. It used to absorb how loose the
 * fit was — see `boundsOf` — so it had to stay small; with the bounds measured
 * per axis it only has to keep the lines off the widget's edge.
 */
export const FIT = 0.92;

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

/**
 * How far the model reaches, measured separately along each axis of the screen.
 *
 * One number will not do, and using one is what made models draw small. A
 * bounding sphere is the furthest any point gets from the origin in any
 * direction at once, which for a tall thin object is set by its *corners* —
 * so an instrument twice as tall as it is wide was being fitted as though it
 * were a ball as wide as it is tall, and then fitted into the shorter side of
 * the widget on top of that. Two separate losses, multiplying.
 *
 * These three are each an upper bound that holds at every angle, so the model
 * still never escapes the widget and still never breathes as it turns.
 */
export type Bounds = {
  /**
   * The furthest any point gets from the upright axis. Spinning moves a point
   * around a circle of exactly this radius, so it is the horizontal half-width
   * whatever the angle.
   */
  radial: number;
  /** The highest any point reaches on screen once the tilt is applied. */
  vertical: number;
  /** The furthest any point gets toward or away from the camera. */
  depth: number;
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
  tiltDegrees: number,
): { moved: Vec3[]; bounds: Bounds } {
  const still: Vec3[] = parts.map(() => [0, 0, 0]);
  const assembled = reachOf(parts, still);
  const furthest = Math.max(
    ...parts.map((part) => Math.hypot(...part.center)),
    0,
  );
  if (explode <= 0 || furthest <= 0 || assembled <= 0)
    return { moved: still, bounds: boundsOf(parts, still, tiltDegrees) };

  const step = (explode * SPREAD * assembled) / furthest;
  const moved = parts.map(
    (part) =>
      [
        part.center[0] * step,
        part.center[1] * step,
        part.center[2] * step,
      ] as Vec3,
  );
  return { moved, bounds: boundsOf(parts, moved, tiltDegrees) };
}

/**
 * Measure the model along each screen axis, at every angle it will ever be at.
 *
 * Walks the actual points rather than bounding the parts, because this is done
 * once when the geometry or the explode changes and never per frame — and the
 * loose version of it is what was costing half the widget.
 *
 * The trick is that spinning is a rotation about the upright axis, so a point
 * at (x, y, z) only ever travels around a circle of radius hypot(x, z). That
 * radius is fixed. Everything else follows from it: horizontally the point
 * never gets further out than that, and vertically the tilt mixes its height
 * with that circle, worst case when the two line up.
 */
export function boundsOf(
  parts: MeshPart[],
  moved: Vec3[],
  tiltDegrees: number,
): Bounds {
  const tilt = (tiltDegrees * Math.PI) / 180;
  const lean = Math.abs(Math.cos(tilt));
  const rise = Math.abs(Math.sin(tilt));
  let radial = 0;
  let vertical = 0;
  let depth = 0;
  parts.forEach((part, at) => {
    const [dx, dy, dz] = moved[at];
    for (let i = 0; i < part.verts.length; i += 3) {
      const r = Math.hypot(part.verts[i] + dx, part.verts[i + 2] + dz);
      const y = Math.abs(part.verts[i + 1] + dy);
      if (r > radial) radial = r;
      // The spun coordinate lands anywhere in [-r, r], so the worst case for
      // each of these is the angle where both terms pull the same way.
      vertical = Math.max(vertical, y * lean + r * rise);
      depth = Math.max(depth, y * rise + r * lean);
    }
  });
  return { radial, vertical, depth };
}

/**
 * The model's overall radius: the furthest any point gets from the origin.
 *
 * Only the explode reads this now, to decide how far a part should travel
 * against the size of the thing it is coming out of. Drawing uses `boundsOf`,
 * which measures per axis — this one number was too blunt to scale by, which
 * is the bug that made every model draw small.
 *
 * Deliberately generous: a part's own radius plus how far its centre has moved.
 * For choosing an explode distance, slightly generous costs nothing.
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
  bounds: Bounds,
): Camera {
  const tilt = (tiltDegrees * Math.PI) / 180;
  // Guarded because a model as deep as the camera is distant would divide by
  // nothing and draw at infinity. Nothing normalised gets near it, but a model
  // that is a single point is reachable by a bad file.
  const depth = Math.min(Math.max(bounds.depth, 1e-6), FOV * 0.6);
  const nearest = FOV / (FOV - depth);
  // Whichever axis runs out first. Solved against the near side rather than the
  // middle, because perspective makes the half of the model closest to the
  // camera bigger than life — fit the middle and the near face spills over the
  // edge, which on a board where nothing may overlap is a wireframe drawn on
  // top of the widget next door.
  const scale = Math.min(
    ((width / 2) * FIT) / (Math.max(bounds.radial, 1e-6) * nearest),
    ((height / 2) * FIT) / (Math.max(bounds.vertical, 1e-6) * nearest),
  );
  return {
    cos: Math.cos(angle),
    sin: Math.sin(angle),
    lean: Math.cos(tilt),
    rise: Math.sin(tilt),
    scale,
    cx: width / 2,
    cy: height / 2,
    reach: depth,
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

/**
 * Where each part sits on a colour wave, or null for a part the wave skips.
 *
 * A position from 0 to 1 along whichever axis the wave runs. Every part holds
 * its own point on the ramp at every moment, so the model always carries the
 * whole gradient and the wave is that gradient travelling — rather than a lit
 * band crossing dark geometry, which leaves most of the object dead at any one
 * instant.
 *
 * "stack" runs bottom to top, and on a model built as a pipeline that is the
 * data going through it.
 *
 * "loop" runs around the upright axis, so parts light in the order they sit
 * around the circle. A part standing ON that axis has no angle to take a turn
 * from and comes back null — which is the useful half of the mode rather than a
 * gap in it: on a model whose loop is a ring of parts around a shaft, this
 * lights the ring and leaves the shaft alone.
 */
export function phases(
  parts: MeshPart[],
  mode: "stack" | "loop",
): (number | null)[] {
  if (mode === "loop") {
    const radial = parts.map((p) => Math.hypot(p.center[0], p.center[2]));
    const widest = Math.max(...radial, 0);
    return parts.map((part, at) =>
      // A tenth of the widest part's offset: far enough off the axis to have a
      // meaningful angle, rather than a part that is centred and jitters.
      widest <= 0 || radial[at] < widest * 0.1
        ? null
        : (Math.atan2(part.center[2], part.center[0]) / (2 * Math.PI) + 1) % 1,
    );
  }
  const heights = parts.map((part) => part.center[1]);
  const low = Math.min(...heights);
  const span = Math.max(...heights) - low;
  // A model whose parts all sit at one height has no stack to run up, so the
  // whole thing pulses together rather than dividing by nothing.
  return heights.map((y) => (span > 0 ? (y - low) / span : 0));
}

/**
 * Which two colours of a ramp a position falls between, and how far.
 *
 * The ramp wraps: the last colour leads back into the first, so a list of three
 * is a cycle rather than a journey that has to jump home. Somebody wanting it
 * to come back the way it went writes the middle colour twice.
 */
export function rampAt(
  count: number,
  t: number,
): { from: number; to: number; mix: number } {
  const at = ((t % 1) + 1) % 1;
  const scaled = at * count;
  const from = Math.floor(scaled) % count;
  return { from, to: (from + 1) % count, mix: scaled - Math.floor(scaled) };
}

/**
 * Which of a widget's colour rules applies to a part, if any.
 *
 * Keys may be globs, and the rule that spells out the most wins — so
 * `refine_block` beats `refine_*` beats `*`, whatever order they were written
 * in. Counted in characters that are not wildcards, rather than in characters:
 * `encoder_3` and `encoder_*` are both nine long, and picking by length made
 * naming a part unable to override the glob that covered it, which is the one
 * thing anybody writes a second rule for.
 */
export function colourFor(
  name: string,
  rules: Record<string, string> | null | undefined,
): string | null {
  if (!rules) return null;
  let best: string | null = null;
  let spelt = -1;
  for (const [pattern, colour] of Object.entries(rules)) {
    const literal = pattern.replace(/[*?]/g, "").length;
    if (literal > spelt && globMatches(pattern, name)) {
      best = colour;
      spelt = literal;
    }
  }
  return best;
}

/** Whether a glob of `*` and `?` matches a name, anchored at both ends. */
function globMatches(pattern: string, name: string): boolean {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&");
  const expr = escaped.replace(/\*/g, ".*").replace(/\?/g, ".");
  return new RegExp(`^${expr}$`).test(name);
}
