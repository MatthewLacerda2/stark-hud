/**
 * The typographic half of a flow: whether an arrow's word can be drawn at all.
 *
 * Split out of `lib/flow.ts` for the reason `flow-ranks.ts` was — it is a
 * different subject. There is no routing in here and no bow: only a word, the
 * room there is for it, and the two ways there can fail to be any. `flow.ts`
 * asks these before it hands an arrow over to be drawn.
 *
 * Everything is measured in **board cells**, never in fractions of the widget,
 * because it is the size on the glass that decides whether a word can be read
 * and a fraction of a 3-cell widget is not the same length as a fraction of a
 * 12-cell one.
 */

import type { Point } from "@/lib/flow";

/**
 * The shortest arrow worth putting any word on, in cells.
 *
 * A cell is roughly 60px on the television this is read from, so one and a half
 * of them is about 90px — below which a label is not small, it is a smudge
 * lying across a line. Measured in cells rather than in fractions because a
 * fraction of a 3-cell widget and a fraction of a 12-cell one are different
 * lengths, and it is the length on the glass that decides.
 */
const LABEL_FLOOR_CELLS = 1.5;

/**
 * How many cells one character of a label needs.
 *
 * `gantt.ts` asks only whether the bar is wide enough, ignoring how long the
 * name is, and it can: a bar's name is clipped by the bar. A link label has
 * nothing to clip it, so a long word on a short arrow overhangs both ends and
 * reads as a mistake in the drawing rather than in the data. Hence the length.
 */
const LABEL_CELLS_PER_CHAR = 0.2;

/**
 * How tall one line of a label is, in cells.
 *
 * The other side of the rectangle `LABEL_CELLS_PER_CHAR` gives the width of. It
 * does not depend on the word, because a label is always one line.
 *
 * The ink, not the line box: the word is centred on its anchor, so what an edge
 * can cut is the height of a character and not the leading above and below it.
 * `text-node-sm` is 4.114% of the widget's width, clamped, which across every
 * widget this board holds lands between a fifth and four tenths of a cell —
 * three tenths sits in the middle of that and errs the safe way, since being a
 * little generous drops a word that would just have fitted, and being a little
 * mean draws one cut in half.
 */
const LABEL_LINE_CELLS = 0.3;

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

/**
 * Whether the word put at this point lands wholly on the widget.
 *
 * `roomy()` asks whether the arrow is long enough to carry the word. This asks
 * the question that comes after it: whether the word, once placed, is on the
 * glass at all. A long arrow bowed out against the widget's edge passes the
 * first and fails this one, and a flow is clipped and never scrolled, so what
 * is left of the word is half a glyph against the boundary — which does not
 * read as a clipped label, it reads as a fault in the renderer.
 *
 * **The box, not the anchor.** A point can sit well inside 0..1 while the word
 * drawn around it does not. The width is the same estimate `roomy()` measures a
 * word by and the height is one line, so this is arithmetic on the payload and
 * the widget's shape: nothing is measured and no DOM is touched.
 *
 * Both axes and all four edges, because which edge is the near one is a fact
 * about the widget rather than about the flow: a diagram running rightwards
 * loops beneath itself and meets the bottom, one running downwards loops to its
 * right and meets the right.
 *
 * What this deliberately does not model is the few pixels `flow.tsx` lifts a
 * label off its line. That lift is a multiple of the line's weight, which is a
 * 180th of the widget's shorter side — smaller than the slack already in the
 * width estimate — and on the way back it points along the flow rather than
 * across it, so it never pushes a word towards the edge the bow is already
 * against.
 */
export function inside(
  label: string,
  at: Point,
  cols: number,
  rows: number,
): boolean {
  const half = {
    x: (label.length * LABEL_CELLS_PER_CHAR) / 2 / cols,
    y: LABEL_LINE_CELLS / 2 / rows,
  };
  return (
    at.x - half.x >= 0 &&
    at.x + half.x <= 1 &&
    at.y - half.y >= 0 &&
    at.y + half.y <= 1
  );
}
