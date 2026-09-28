/**
 * Words written beside points of a 3D model: which ones, and where they go.
 *
 * A model file may name a point — "at layer 5 the model would say *Paris*" — by
 * giving a node a label. three.js works out where that node lands on the widget
 * every frame; what is decided here is everything after that, and none of it
 * touches three.js or the DOM, so all of it can be tested.
 *
 * A label is flat, like everything else on the board. It is screen-space text at
 * the board's own type size, and it does not shrink, dim or blur with distance:
 * the model is drawn onto a flat sheet, and so are the words beside it.
 */

/** A point on the widget, in pixels from its top-left corner. */
export type Spot = { x: number; y: number };

/** How big a label is drawn, in pixels. Measured, not estimated. */
export type Size = { w: number; h: number };

/** Where a label's top-left corner goes, in pixels. */
export type Placed = { x: number; y: number };

/**
 * The room between a point and its word, and between two words, as a fraction
 * of one line's height.
 *
 * Against the line rather than in pixels because the type grows with the
 * widget, and a gap that stays the same while the words double reads as the
 * words touching.
 */
export const GAP = 0.4;

/**
 * The label a node carries, or null for one it does not.
 *
 * It comes from the node's `extras.label` in a glTF file, which three.js hands
 * over as the object's `userData` — and which Blender writes from a custom
 * property called `label` on the object. Extras rather than a naming convention
 * because a node's name is already a key: `colors` matches parts by name, and a
 * name made to carry a sentence would have to be written out in full in every
 * colour rule that wants that part.
 *
 * A number is a label too — Blender's custom properties are typed, and a layer
 * numbered 5 is more naturally an integer there than a string.
 */
export function labelOf(userData: unknown): string | null {
  if (typeof userData !== "object" || userData === null) return null;
  const label = (userData as { label?: unknown }).label;
  if (typeof label === "number" && Number.isFinite(label)) return String(label);
  if (typeof label !== "string") return null;
  const trimmed = label.trim();
  return trimmed === "" ? null : trimmed;
}

/**
 * Where each label goes on a widget this size, or null for each that does not.
 *
 * Beside its point: to the right, vertically centred on it, which is where a
 * map puts a town's name. Against the right edge it goes to the left of the
 * point instead, and it is held inside the widget top and bottom, so a word is
 * never cut by the widget's edge — half a word reads as a fault, not as a
 * label.
 *
 * **Crowding is settled in the file's order.** Labels are placed first to last,
 * and one that would touch a label already placed is left out for that frame.
 * The first label in the file therefore always wins, which is the one rule that
 * is the same from one frame to the next: an order by depth or by size would
 * have two labels trading places as the model turns. Whoever builds the file
 * decides what matters most by putting it first.
 *
 * A point off the widget, or behind the camera (`null`), has no label drawn.
 *
 * The cost is one box test per label already placed, and the number placed is
 * bounded by how many words fit on the widget at all — a few dozen — so a cloud
 * of a thousand labelled points is still tens of thousands of tests a frame.
 */
export function placeLabels(
  spots: (Spot | null)[],
  sizes: Size[],
  width: number,
  height: number,
): (Placed | null)[] {
  const taken: { x: number; y: number; w: number; h: number; gap: number }[] =
    [];
  return spots.map((spot, at) => {
    const size = sizes[at];
    if (!spot || !size || !onWidget(spot, width, height)) return null;
    const gap = size.h * GAP;
    if (size.w + gap > width || size.h > height) return null;
    const right = spot.x + gap;
    const x = right + size.w <= width ? right : spot.x - gap - size.w;
    if (x < 0) return null;
    const y = Math.min(Math.max(spot.y - size.h / 2, 0), height - size.h);
    const box = { x, y, w: size.w, h: size.h, gap };
    if (taken.some((other) => touching(box, other))) return null;
    taken.push(box);
    return { x, y };
  });
}

/** Whether a point is on the widget at all. */
function onWidget(spot: Spot, width: number, height: number): boolean {
  return spot.x >= 0 && spot.x <= width && spot.y >= 0 && spot.y <= height;
}

/** Whether two boxes come closer than the larger of their gaps. */
function touching(
  a: { x: number; y: number; w: number; h: number; gap: number },
  b: { x: number; y: number; w: number; h: number; gap: number },
): boolean {
  const gap = Math.max(a.gap, b.gap);
  return (
    a.x < b.x + b.w + gap &&
    b.x < a.x + a.w + gap &&
    a.y < b.y + b.h + gap &&
    b.y < a.y + a.h + gap
  );
}
