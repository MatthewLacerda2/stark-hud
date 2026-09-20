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

/**
 * How near a whole cell an edge has to come before it is pulled onto it.
 *
 * A quarter of a cell, about fifteen pixels on the television. Inside that the
 * edge lands on the whole number; outside it, the widget is exactly where the
 * pointer left it, to the decimal.
 *
 * This is what "soft" means. Rounding every position to the nearest cell is not
 * soft snapping, it is the grid the board just spent two issues getting rid of:
 * it makes the fractional coordinates unreachable by hand, which is what they
 * were for. A magnet leaves most of the travel free and still lands a widget
 * flush when somebody meant it to be flush.
 */
const PULL = 0.25;

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

/**
 * Pull an edge onto the old cell size, if it came close enough to one.
 *
 * Purely an affordance of the hand: nothing is rounded on the way to the server,
 * so what a widget shows is where it is. It exists because a board arranged by
 * hand looks accidentally crooked from across a room, and whole numbers are what
 * the grid used to give for free — but it has to leave the rest of the board
 * reachable, or the coordinates may as well still be integers.
 */
function pulled(value: number, snap: boolean): number {
  if (!snap) return value;
  const whole = Math.round(value);
  return Math.abs(value - whole) <= PULL ? whole : value;
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

/**
 * Two edges that ought to meet arrive as sums of decimals, and 0.1 + 0.2 is not
 * 0.3. Anything closer together than this is the same edge, not an overlap —
 * the same number, for the same reason, as `_EPS` in `services/placement.py`.
 */
const EPS = 1e-9;

/**
 * How much of itself a widget may have swallowed before it gives up and goes
 * home.
 *
 * Measured against the dragged widget's own area, summed over everything it
 * landed on, so a drop behaves the same whether it clipped something big or
 * something small. A fifth is about the most a person can cover and still have
 * meant the gap rather than the widget: past that they were aiming at what is
 * already there, and the spring back is the honest answer.
 */
const SWALLOWED = 0.2;

/**
 * The least of itself a widget may keep when it shrinks into a gap.
 *
 * `MIN_SIZE` is the board's hard floor and says nothing about legibility: a
 * widget shrunk until it still fits the rules can stop saying what it said. The
 * VRAM gauge is the one that found this — its label abbreviates when it gets
 * short, so a silent quarter off is already the edge of a widget meaning what
 * it meant. Below three quarters the widget goes home instead.
 */
const KEPT = 0.75;

/** The board a widget is being put on, in columns and rows. */
type Board = { cols: number; rows: number };

/** The same rectangle with its axes swapped, so one magnet serves both. */
function flipped(rect: Rect): Rect {
  return { x: rect.y, y: rect.x, w: rect.h, h: rect.w };
}

/** How much of these two rectangles is in the same place, in cells. */
function overlap(a: Rect, b: Rect): number {
  const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return w > EPS && h > EPS ? w * h : 0;
}

/** Whether this rectangle is on the board and on nobody. */
function free(rect: Rect, neighbours: Rect[], board: Board): boolean {
  if (rect.x < -EPS || rect.y < -EPS) return false;
  if (rect.x + rect.w > board.cols + EPS) return false;
  if (rect.y + rect.h > board.rows + EPS) return false;
  return neighbours.every((n) => overlap(rect, n) === 0);
}

/** How much of the dragged widget its neighbours have, as a share of itself. */
function swallowed(rect: Rect, neighbours: Rect[]): number {
  const area = rect.w * rect.h;
  if (area <= EPS) return 0;
  return neighbours.reduce((sum, n) => sum + overlap(rect, n), 0) / area;
}

/**
 * Where this widget's near edge would like to be, given what it is beside.
 *
 * The cell magnet in `pulled` has already run on the pointer; this is the
 * second half of the same idea, and the issue asked for both: a neighbour's
 * edge is worth landing on for exactly the reason a whole column is. Every
 * neighbour offers two lines, its own two edges, and the widget can meet each
 * of them with either of its own — so it lands flush against a neighbour or
 * lined up with one, whichever is nearer, and only ever moves a quarter cell to
 * do it.
 *
 * Only the widgets it could actually meet: one four rows away shares no part of
 * this row, so its edges are not edges this widget can come to rest against,
 * and pulling towards them is a tug with no reason on the screen for it.
 *
 * Written for the x axis alone and called twice, the second time on a board
 * turned on its side. Rectangles are symmetrical and the rule is too.
 */
function attracted(rect: Rect, neighbours: Rect[], limit: number): number {
  const beside = neighbours.filter(
    (n) => n.y + n.h > rect.y + EPS && rect.y + rect.h > n.y + EPS,
  );
  const seat = beside
    .flatMap((n) => [n.x, n.x + n.w])
    .flatMap((edge) => [edge, edge - rect.w])
    .filter((x) => x >= -EPS && x + rect.w <= limit + EPS)
    .map((x) => ({ x, gap: Math.abs(x - rect.x) }))
    .filter((s) => s.gap <= PULL + EPS)
    // Nearest wins; the leftmost of two equally near, so the same drop always
    // settles the same way rather than on whichever widget was listed first.
    .sort((a, b) => a.gap - b.gap || a.x - b.x)
    .at(0);
  return seat?.x ?? rect.x;
}

/** The widget pulled onto the lines its neighbours offer, on both axes. */
function magnetised(rect: Rect, neighbours: Rect[], board: Board): Rect {
  const near = {
    ...rect,
    x: attracted(rect, neighbours, board.cols),
    y: attracted(flipped(rect), neighbours.map(flipped), board.rows),
  };
  // A magnet that pulls a widget further into somebody is not a magnet worth
  // having. Lining an edge up is a tidiness, and it may not make the drop
  // harder to rescue than it already was — lining a small widget's left edge up
  // with a big one's swallows it whole, and the answer would be a spring back
  // to a drop that was perfectly rescuable.
  return swallowed(near, neighbours) > swallowed(rect, neighbours) + EPS
    ? rect
    : near;
}

/**
 * The two ways out of an overlap: back out sideways, or back out downwards.
 *
 * On each axis a widget leaves the way it came in — whichever of the two
 * directions is the shorter, which is the one where it is least far in. The
 * other direction on that axis is not a way out at all but a way *through*,
 * and pushing a widget out the far side of a neighbour is how it ends up
 * against something on the other side of the screen. A drop that lands
 * somewhere else entirely is worse than one that refuses, because the refusal
 * at least happens where the hand is.
 *
 * Ties, and there are two kinds. Within an axis, back out west or north — the
 * top-left, which is the order the server searches its own slots in. Between
 * the axes, go sideways: the board is 32 columns by 18 rows, so rows are the
 * scarcer of the two and a widget is likelier to find room across than down.
 * Some order has to win, and a coin toss reads as a bug from across the room.
 */
function ways(rect: Rect, hit: Rect[]): { to: Rect; travel: number }[] {
  const west = Math.max(...hit.map((n) => rect.x + rect.w - n.x));
  const east = Math.max(...hit.map((n) => n.x + n.w - rect.x));
  const north = Math.max(...hit.map((n) => rect.y + rect.h - n.y));
  const south = Math.max(...hit.map((n) => n.y + n.h - rect.y));
  const across = west <= east ? -west : east;
  const down = north <= south ? -north : south;
  return [
    { to: { ...rect, x: rect.x + across }, travel: Math.abs(across) },
    { to: { ...rect, y: rect.y + down }, travel: Math.abs(down) },
  ].sort((a, b) => a.travel - b.travel);
}

/**
 * The four edges the widget could give up instead of moving, and what is left
 * of it if it does.
 *
 * One edge, never two: a widget trimmed on both axes at once has been reshaped
 * rather than fitted, and nobody dropping it asked for that.
 */
function trims(rect: Rect, hit: Rect[]): Rect[] {
  const right = Math.min(...hit.map((n) => n.x - rect.x));
  const bottom = Math.min(...hit.map((n) => n.y - rect.y));
  const left = Math.max(...hit.map((n) => n.x + n.w));
  const top = Math.max(...hit.map((n) => n.y + n.h));
  return [
    { ...rect, w: right },
    { ...rect, h: bottom },
    { ...rect, x: left, w: rect.x + rect.w - left },
    { ...rect, y: top, h: rect.y + rect.h - top },
  ];
}

/** Whether a shrunk widget is still enough of itself to be worth landing. */
function enough(
  small: Rect,
  whole: Rect,
  neighbours: Rect[],
  board: Board,
): boolean {
  if (small.w < MIN_SIZE - EPS || small.h < MIN_SIZE - EPS) return false;
  if (small.w * small.h < KEPT * whole.w * whole.h - EPS) return false;
  return free(small, neighbours, board);
}

/**
 * Where a held widget comes to rest among the ones already on the board, or
 * `null` when there is nowhere for it and it goes back where it came from.
 *
 * The board is 99.6 % full, so a drop that has to be perfect is a drop that
 * springs back, and springing back is silent geometry the screen never
 * explains. So a widget carried over a gap attaches to it: it lines up with
 * what it is beside, slides off anything it clipped, and gives up a little of
 * itself if the gap is nearly big enough. Dropped squarely on top of something
 * it still goes home, which is the one case that should feel like a refusal.
 *
 * Nothing is drawn to say any of this. The widget is simply where a person
 * meant to put it by the time they let go — see decision 4 on issue #154: the
 * gesture is already showing the answer, so releasing changes nothing.
 *
 * `neighbours` is what is drawn beside it and nothing else. A widget on a page
 * that is not showing is not there to be bumped into, a folded group is one
 * widget rather than the several it holds, and both of those are already true
 * of the list the board renders from — see `onBoard(onPage(...))`.
 *
 * The server is still the judge. This proposes a rectangle it believes is
 * legal; `placement.illegal` decides, and a refusal still sends the widget
 * home.
 */
export function landed(
  rect: Rect,
  neighbours: Rect[],
  board: Board,
  snap: boolean,
): Rect | null {
  const wanted = snap ? magnetised(rect, neighbours, board) : rect;
  if (free(wanted, neighbours, board)) return wanted;
  const hit = neighbours.filter((n) => overlap(wanted, n) > 0);
  if (hit.length === 0) return null;
  if (swallowed(wanted, neighbours) > SWALLOWED + EPS) return null;
  const slid = ways(wanted, hit).find((way) => free(way.to, neighbours, board));
  if (slid) return slid.to;
  // Nowhere to slide to, so the gap is smaller than the widget. It may have up
  // to a quarter of itself taken off to fit; the biggest survivor wins.
  return (
    trims(wanted, hit)
      .filter((small) => enough(small, wanted, neighbours, board))
      .sort((a, b) => b.w * b.h - a.w * a.h)
      .at(0) ?? null
  );
}
