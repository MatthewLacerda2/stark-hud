/**
 * The arithmetic behind a mesh widget, with no three.js in it.
 *
 * three.js draws the model; what is decided here is everything that is a rule
 * rather than a rendering — which file loader a path wants, where the model
 * faces after so many seconds, how far back the camera stands to fit it, how
 * far each part moves when it is pulled apart, which colour a part takes. All of
 * it pure and frame-independent: given a time it says where things are, and it
 * never asks what time it is. `lib/hologram.ts` owns the scene; the component
 * owns the clock.
 */

/** A point, and a part's centre. */
export type Vec3 = [number, number, number];

/**
 * How much of the widget the model spans at its widest.
 *
 * A margin rather than a fudge factor: the fit is measured, so this only has to
 * keep the glow of the outermost lines off the widget's edge.
 */
export const FIT = 0.92;

/**
 * How far apart a fully exploded model's parts end up, against its size.
 *
 * At 1 each part travels out along the line from the middle of the model by
 * this much of the model's own radius, scaled so the part furthest out goes
 * furthest. Well short of 1 on purpose: parts that leave the model's outline
 * entirely stop reading as pieces of one thing.
 */
export const SPREAD = 0.6;

/** The kinds of file a mesh widget reads, by the loader each one needs. */
export type ModelFormat = "gltf" | "obj" | "fbx";

/**
 * Which loader a model's path wants, or null for one no loader here reads.
 *
 * A `.glb` and a `.gltf` go to the same loader, which tells them apart by their
 * first bytes. The backend refuses anything else before a widget exists, so
 * null is a board file somebody edited by hand.
 */
export function formatOf(path: string): ModelFormat | null {
  const suffix = path.slice(path.lastIndexOf(".")).toLowerCase();
  if (suffix === ".glb" || suffix === ".gltf") return "gltf";
  if (suffix === ".obj") return "obj";
  if (suffix === ".fbx") return "fbx";
  return null;
}

/**
 * Where the model is pointing after `seconds`, in radians, before `heading`.
 *
 * With no sweep it goes round: `spin` turns per second, forever — and at the
 * default of 0, not at all. With a sweep it swings instead — out to `sweep`
 * degrees one way, back through the middle to the same angle the other way,
 * and again — because a model with a front spends three quarters of a full
 * turn showing something else. `spin` still sets the pace, as one
 * there-and-back per 1/spin seconds.
 *
 * The swing is a triangle wave put through a smootherstep, so it eases into
 * each end and reverses without a jolt: the easing has zero velocity and zero
 * acceleration at both ends.
 */
export function heading(seconds: number, spin: number, sweep: number): number {
  if (sweep <= 0) return seconds * spin * Math.PI * 2;
  if (spin === 0) return 0;
  const cycle = (((seconds * Math.abs(spin)) % 1) + 1) % 1;
  const there = cycle < 0.5 ? cycle * 2 : 2 - cycle * 2;
  const eased = there * there * there * (there * (there * 6 - 15) + 10);
  return Math.sign(spin) * ((sweep * Math.PI) / 180) * (eased * 2 - 1);
}

/**
 * How far from a sphere's middle a camera has to stand to see all of it.
 *
 * The narrower of the two fields of view decides, so a model in a tall widget
 * is fitted to the width and one in a wide widget to the height. Standing
 * `radius / sin(half)` away puts the sphere's edge exactly on the view's edge;
 * `FIT` leaves the margin.
 */
export function fitDistance(
  radius: number,
  fovDegrees: number,
  aspect: number,
): number {
  const vertical = (fovDegrees * Math.PI) / 180;
  const horizontal = 2 * Math.atan(Math.tan(vertical / 2) * aspect);
  const half = Math.min(vertical, horizontal) / 2;
  return radius / Math.sin(half) / FIT;
}

/**
 * How far each part moves when the model is pulled apart.
 *
 * Each part travels straight out along the line from the middle of the model to
 * the middle of that part, which is what an exploded diagram has always done:
 * things come apart the way they went together. Scaled so the part furthest out
 * travels `explode * SPREAD * radius`.
 *
 * Two parts with the same centre never separate, and no arithmetic here can fix
 * that: concentric rings genuinely share a middle. That is a property of the
 * model, and the answer is to give them different depths when modelling.
 */
export function explodeOffsets(
  centers: Vec3[],
  radius: number,
  explode: number,
): Vec3[] {
  const furthest = Math.max(...centers.map((c) => Math.hypot(...c)), 0);
  if (explode <= 0 || furthest <= 0 || radius <= 0)
    return centers.map(() => [0, 0, 0]);
  const step = (explode * SPREAD * radius) / furthest;
  return centers.map(([x, y, z]) => [x * step, y * step, z * step]);
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
  centers: Vec3[],
  mode: "stack" | "loop",
): (number | null)[] {
  if (mode === "loop") {
    const radial = centers.map(([x, , z]) => Math.hypot(x, z));
    const widest = Math.max(...radial, 0);
    return centers.map(([x, , z], at) =>
      // A tenth of the widest part's offset: far enough off the axis to have a
      // meaningful angle, rather than a part that is centred and jitters.
      widest <= 0 || radial[at] < widest * 0.1
        ? null
        : (Math.atan2(z, x) / (2 * Math.PI) + 1) % 1,
    );
  }
  const heights = centers.map(([, y]) => y);
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
 * Which of a widget's colour rules applies to a name, if any.
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

/**
 * The colour rule for something drawn, found on it or on what holds it.
 *
 * `names` runs from the drawn object outward to the model's root. The nearest
 * name any rule matches decides, so a rule on `gpu` colours everything inside
 * the card unless something inside it — `gpu_fan_1` — has a rule of its own.
 */
export function colourUp(
  names: string[],
  rules: Record<string, string> | null | undefined,
): string | null {
  for (const name of names) {
    const found = colourFor(name, rules);
    if (found !== null) return found;
  }
  return null;
}

/** Whether a glob of `*` and `?` matches a name, anchored at both ends. */
function globMatches(pattern: string, name: string): boolean {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&");
  const expr = escaped.replace(/\*/g, ".*").replace(/\?/g, ".");
  return new RegExp(`^${expr}$`).test(name);
}
