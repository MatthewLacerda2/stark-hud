/**
 * Where the call that made a widget is drawn.
 *
 * Beside it, over the board, taking no room. The board is finite and never
 * scrolls, so nothing that appears for two seconds may be able to make it
 * fuller: this never claims a cell, never moves a widget and never enters the
 * arithmetic that decides where widgets go. It is a rectangle in the same
 * coordinate space, worked out from the widget's own and drawn on top.
 *
 * No React and no DOM, the way `lib/entrance.ts` and `lib/drag.ts` have none.
 * Everything here is arithmetic on rectangles and can be read and tested
 * without a browser — which matters more than usual, because what this produces
 * is only ever seen for two seconds at a time on a television.
 */
import type { Rect } from "@/lib/drag";

/** The board's own size, in columns and rows. */
type Board = { cols: number; rows: number };

/**
 * The panel's size, as a share of the board.
 *
 * A share rather than a number of cells because the board's size is read from
 * the server and has already changed once: eight columns of thirty-two is a
 * quarter of the screen, and it should stay a quarter however many columns
 * there turn out to be.
 *
 * Deliberately a little shorter than the text it holds. Two rows of eighteen is
 * about four lines of the small type, and the server cuts a call to roughly
 * six — so a long one drifts up through the panel over its two seconds and a
 * short one sits still, which is the nicer case. A panel tall enough for
 * everything would never move, and a thing that never moves on a board is a
 * label.
 */
const WIDE = 1 / 4;
const TALL = 1 / 9;

/** Keep `value` inside `[low, high]`. */
function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high);
}

/**
 * Where the call sits for the widget that landed at `rect`.
 *
 * The side with screen room wins, and the wider side wins a tie, so a widget
 * against the left wall is described from its right and one in the middle from
 * whichever half of the board is emptier. When neither side can hold the panel
 * it goes over the widget itself — a call drawn across what it made is still
 * legible as a call, and one hanging half off the screen is not.
 *
 * It is not kept clear of other widgets, unlike a flight in `lib/entrance.ts`.
 * A flight has to read as one thing travelling and cannot pass through another;
 * this takes no pointer, is gone in two seconds and is texture over the board
 * rather than part of it.
 */
export function beside(rect: Rect, board: Board): Rect {
  const w = board.cols * WIDE;
  const h = board.rows * TALL;
  const west = rect.x;
  const east = board.cols - (rect.x + rect.w);

  const x =
    east >= w && east >= west
      ? rect.x + rect.w
      : west >= w
        ? rect.x - w
        : clamp(rect.x + (rect.w - w) / 2, 0, board.cols - w);

  // Level with the widget's top, which reads as belonging to it, and never
  // below the board's bottom edge.
  return { x, y: clamp(rect.y, 0, board.rows - h), w, h };
}
