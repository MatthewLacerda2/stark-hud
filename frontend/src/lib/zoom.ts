/**
 * Zooming a picture about a point, as arithmetic.
 *
 * The picture is drawn at `translate(x, y) scale(scale)` from its top-left
 * corner, so a point on screen `p` shows the picture's point `(p - x) / scale`.
 * Zooming keeps whatever is under the pointer under the pointer — the one thing
 * that makes a wheel zoom feel like reaching into the picture rather than
 * losing your place in it.
 *
 * No React and no DOM, like `lib/origin.ts`.
 */

export type View = { scale: number; x: number; y: number };

export const WHOLE: View = { scale: 1, x: 0, y: 0 };

/** Never smaller than fitting the screen: there is nothing to see out there. */
const LEAST = 1;
/** Twenty times is past the pixels of any sheet this board hangs. */
const MOST = 20;

/** The view after zooming by `factor` with the point `(px, py)` held still. */
export function zoomAt(
  view: View,
  factor: number,
  px: number,
  py: number,
): View {
  const scale = Math.min(MOST, Math.max(LEAST, view.scale * factor));
  if (scale === LEAST) return WHOLE;
  const kept = scale / view.scale;
  return { scale, x: px - (px - view.x) * kept, y: py - (py - view.y) * kept };
}

/** How much one wheel step zooms. A notch of a mouse wheel is about 100. */
export function wheelFactor(deltaY: number): number {
  return Math.exp(-deltaY * 0.0015);
}
