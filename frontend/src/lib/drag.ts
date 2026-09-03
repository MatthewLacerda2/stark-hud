/**
 * The geometry of moving and resizing a widget, with no React and no DOM in it.
 *
 * The board is a space rather than a set of slots, so a gesture is arithmetic on
 * two rectangles: where the widget started and how far the pointer has come, in
 * columns and rows. Everything that decides what a drag means lives here, which
 * is why it can be read and tested without a browser.
 *
 * Nothing here asks whether the result is free. The server owns that, refuses an
 * overlap, and the widget goes back where it was — the same answer a session
 * gets from `move_item`.
 */

/**
 * The smallest a widget may be, in cells.
 *
 * Mirrors `MIN_SIZE` in the backend's `schemas/board.py`. Kept in step by hand
 * because the two never move: the number is a fact about a television read from
 * a sofa, not a setting.
 */
export const MIN_SIZE = 0.25;

/** What a pointer took hold of: the widget itself, or one of its eight edges. */
export type Grip = "move" | "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

/** Where a widget is, in columns and rows. The same four numbers the server has. */
export type Rect = { x: number; y: number; w: number; h: number };

/** How far a pointer has travelled, in columns and rows rather than pixels. */
export type Travel = { x: number; y: number };

/** Sides resize one axis, corners resize both. */
export const EDGES = ["n", "s", "e", "w", "ne", "nw", "se", "sw"] as const;

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

/**
 * Pull an edge onto the old cell size.
 *
 * Purely an affordance of the hand: nothing is rounded on the way to the server,
 * so what a widget shows is where it is. It exists because a board arranged by
 * hand looks accidentally crooked from across a room, and whole numbers are what
 * the grid used to give for free.
 */
function pulled(value: number, snap: boolean): number {
  return snap ? Math.round(value) : value;
}

/** The widget moved bodily, kept inside the board. */
function moved(
  start: Rect,
  by: Travel,
  cols: number,
  rows: number,
  snap: boolean,
): Rect {
  return {
    ...start,
    x: clamp(pulled(start.x + by.x, snap), 0, cols - start.w),
    y: clamp(pulled(start.y + by.y, snap), 0, rows - start.h),
  };
}

/**
 * One axis resized by dragging an edge.
 *
 * Returned as the new start and length of that axis. The far edge never moves,
 * and the near one stops at the wall in one direction and at `MIN_SIZE` in the
 * other — a widget dragged shut becomes small, never inside out.
 */
function pinched(
  start: number,
  length: number,
  by: number,
  limit: number,
  near: boolean,
  snap: boolean,
): [number, number] {
  if (near) {
    const edge = clamp(pulled(start + by, snap), 0, start + length - MIN_SIZE);
    return [edge, start + length - edge];
  }
  const edge = clamp(
    pulled(start + length + by, snap),
    start + MIN_SIZE,
    limit,
  );
  return [start, edge - start];
}

/**
 * Where a widget ends up, given where it started and how far the pointer went.
 *
 * `by` is in columns and rows, not pixels: the caller divides by the size of a
 * cell, which is the one thing that needs to know how big the screen is.
 */
export function dragged(
  start: Rect,
  grip: Grip,
  by: Travel,
  board: { cols: number; rows: number },
  snap: boolean,
): Rect {
  if (grip === "move") return moved(start, by, board.cols, board.rows, snap);

  let { x, y, w, h } = start;
  if (grip.includes("w") || grip.includes("e")) {
    [x, w] = pinched(
      start.x,
      start.w,
      by.x,
      board.cols,
      grip.includes("w"),
      snap,
    );
  }
  if (grip.includes("n") || grip.includes("s")) {
    [y, h] = pinched(
      start.y,
      start.h,
      by.y,
      board.rows,
      grip.includes("n"),
      snap,
    );
  }
  return { x, y, w, h };
}

/** Whether a gesture ended up asking for anything at all. */
export function same(a: Rect, b: Rect): boolean {
  return a.x === b.x && a.y === b.y && a.w === b.w && a.h === b.h;
}
