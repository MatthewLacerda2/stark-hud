/**
 * How a widget gets onto the board, and how it gets off again.
 *
 * A thing that travels has come from somewhere; a thing that grows in place
 * came from nowhere. So a widget flies in from the edge of the screen when it
 * can, and grows out of nothing when it cannot — and "can" is a clear corridor.
 *
 * The corridor is the widget's own rectangle swept from where it lands to off
 * the board, along one axis. If another widget is inside it the flight would
 * pass straight over a neighbour, so that edge is closed. All four are tested
 * and the nearest open one wins, because a widget on the left should not cross
 * the whole board to get home.
 *
 * No React and no DOM, the way `lib/drag.ts` has none: everything that decides
 * what an arrival means is arithmetic on rectangles, and can be read and tested
 * without a browser.
 *
 * Nothing here is stored and nothing here is asked for. The board records where
 * things end up, never where they are mid-flight, and which way a widget came
 * in is not a choice a session makes — it falls out of where the widget landed
 * and what was already there.
 */
import type { Rect } from "@/lib/drag";

/** The board's own size, in columns and rows. */
type Board = { cols: number; rows: number };

/** An edge of the screen, named the way a resize grip is. */
export type Side = "w" | "e" | "n" | "s";

/**
 * The order ties are broken in, and the whole of what makes this deterministic.
 *
 * Two edges come out exactly as near whenever a widget is centred on an axis,
 * which on a board arranged by hand is common rather than freakish. West before
 * east because that is the side reading starts on; the horizontal pair before
 * the vertical one because the screen is wider than it is tall, so sideways is
 * the longer, more legible travel. The reasons matter less than the fact that
 * the order never changes: the same board animates the same way every time.
 */
const ORDER: readonly Side[] = ["w", "e", "n", "s"];

/**
 * Which way a widget came in.
 *
 * `edge` is null when it was boxed in on all four sides and had to grow in
 * place. `dx` and `dy` are where the flight starts, as multiples of the
 * widget's own width and height — which is what a CSS `translate` percentage
 * means, so the board never has to know how big the screen is.
 */
export type Entrance = { edge: Side | null; dx: number; dy: number };

/** Rectangles overlap only if they share area. Touching edge to edge does not. */
function overlaps(a: Rect, b: Rect): boolean {
  return (
    a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
  );
}

/**
 * The widget's own rectangle swept from where it lands to off the board.
 *
 * Only the part still on the board, which is the only part anything can be in
 * the way of. Its length along the axis of travel is the travel itself — the
 * corridor and the distance are the same measurement, taken once.
 */
function corridor(rect: Rect, side: Side, board: Board): Rect {
  switch (side) {
    case "w":
      return { x: 0, y: rect.y, w: rect.x + rect.w, h: rect.h };
    case "e":
      return { x: rect.x, y: rect.y, w: board.cols - rect.x, h: rect.h };
    case "n":
      return { x: rect.x, y: 0, w: rect.w, h: rect.y + rect.h };
    case "s":
      return { x: rect.x, y: rect.y, w: rect.w, h: board.rows - rect.y };
  }
}

/** How far the widget has to travel to be entirely off that side. */
function travel(box: Rect, side: Side): number {
  return side === "w" || side === "e" ? box.w : box.h;
}

/** Where the flight starts, as a multiple of the widget's own size. */
function from(rect: Rect, side: Side, distance: number): Entrance {
  switch (side) {
    case "w":
      return { edge: side, dx: -distance / rect.w, dy: 0 };
    case "e":
      return { edge: side, dx: distance / rect.w, dy: 0 };
    case "n":
      return { edge: side, dx: 0, dy: -distance / rect.h };
    case "s":
      return { edge: side, dx: 0, dy: distance / rect.h };
  }
}

/**
 * The nearest clear corridor to an edge, or none at all.
 *
 * `others` is the board as it stands: everything except this widget. On the way
 * in that is the board it is joining, and on the way out it is the board it is
 * leaving behind, recomputed at that moment — so a widget goes out by a way it
 * could have come in, even if the board has changed since it arrived.
 */
export function entrance(rect: Rect, others: Rect[], board: Board): Entrance {
  let best: Entrance = { edge: null, dx: 0, dy: 0 };
  let least = Infinity;

  for (const side of ORDER) {
    const swept = corridor(rect, side, board);
    const distance = travel(swept, side);
    // A later side has to be strictly nearer to displace an earlier one, which
    // is what makes ORDER the tie-break rather than a coincidence of looping.
    if (distance >= least) continue;
    if (others.some((other) => overlaps(swept, other))) continue;
    best = from(rect, side, distance);
    least = distance;
  }

  return best;
}

/**
 * The custom properties the flight reads: where it starts, in its own sizes.
 *
 * A `transform`, never a change of `left`/`top`. The widget is positioned as a
 * share of the board and `widget-settle` already transitions those four
 * properties — animating them here would collide with the settle and make the
 * arrival a layout change. A translate costs no layout and cannot disturb
 * anything else on the board.
 */
export function entranceVars(flight: Entrance): Record<string, string> {
  return {
    "--fly-x": `${(flight.dx * 100).toFixed(2)}%`,
    "--fly-y": `${(flight.dy * 100).toFixed(2)}%`,
  };
}

/** The class that plays this entrance, or plays it backwards on the way out. */
export function entranceClass(flight: Entrance, going: boolean): string {
  if (going) return flight.edge ? "widget-flying-out" : "widget-leaving";
  return flight.edge ? "widget-flying-in" : "widget-arriving";
}
