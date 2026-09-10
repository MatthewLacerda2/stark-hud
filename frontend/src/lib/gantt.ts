import type { GanttBar, GanttRow } from "@/lib/schemas/board";

/**
 * Reading a gantt: how wide the window is, where each bar sits in it, and
 * whether a bar has room for its own name.
 *
 * All of it is a function of the bars and the current time, and none of it is
 * stored. The board keeps the instants because those are facts a browser cannot
 * know; the geometry is a reading, and this is where it is taken — the same
 * division `lib/countdown.ts` makes, for the same reason.
 *
 * No React and no DOM, so the arithmetic can be tested without a browser.
 */

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const WEEK = 7 * DAY;

/**
 * The widths the window is allowed to be.
 *
 * Snapped and never fitted, so the frame is one you recognise rather than one
 * that slides: the same task looks like the same amount of work between two
 * glances across the room. Five minutes is the floor — when the only thing left
 * is two minutes from ending, showing the next two would make one bar the whole
 * widget and say nothing.
 *
 * There is no ceiling. Past four weeks the ladder keeps doubling, because if
 * the only thing left is three months out then three months is the honest
 * reading, and the alternative is clipping it off the screen entirely.
 */
export const STEPS = [
  5 * MINUTE,
  10 * MINUTE,
  15 * MINUTE,
  30 * MINUTE,
  HOUR,
  2 * HOUR,
  4 * HOUR,
  8 * HOUR,
  12 * HOUR,
  DAY,
  2 * DAY,
  3 * DAY,
  WEEK,
  2 * WEEK,
  3 * WEEK,
  4 * WEEK,
];

/**
 * How many of the nearest bars the window has to cover.
 *
 * Covering *the next few* rather than *everything* is what stops one distant
 * bar from crushing tonight into a hairline. Three is enough to see what is
 * running and what is next, which is what a glance is for.
 */
export const COVERS = 3;

/**
 * How much of the widget's width the row names take.
 *
 * One number, read twice: the stylesheet lays the column out with it and
 * `roomy` subtracts it before deciding whether a bar can hold a word. Two
 * copies of it would disagree the first time either moved.
 */
export const NAMES = 0.18;

/**
 * The narrowest a bar can be and still be worth putting a word in, in cells.
 *
 * A cell is roughly 60px on the television this is read from, so two of them is
 * about 120px — a word or two at the size these are drawn. Below that the name
 * is not small, it is absent: there is no font size at which "do the sauce"
 * fits into fifteen minutes of a four-hour window.
 */
export const TITLE_CELLS = 2;

/** When a bar is over. */
function finish(bar: GanttBar): number {
  return new Date(bar.end).getTime();
}

/** Every bar not yet over, soonest to finish first. */
export function ahead(rows: GanttRow[], now: number): GanttBar[] {
  return rows
    .flatMap((row) => row.bars)
    .filter((bar) => finish(bar) > now)
    .sort((a, b) => finish(a) - finish(b));
}

/** The smallest step that covers this much time, doubling past the last rung. */
export function step(need: number): number {
  const rung = STEPS.find((width) => width >= need);
  if (rung !== undefined) return rung;
  let width = STEPS[STEPS.length - 1];
  while (width < need) width *= 2;
  return width;
}

/**
 * How wide the window is: the smallest step covering the next few bars.
 *
 * It re-tunes itself as the clock passes each of them, which is the whole
 * point. An evening with three things inside the hour is drawn an hour wide;
 * half an hour later, with only one thing left and it four hours out, the same
 * widget is four hours wide rather than staying zoomed into an hour that has
 * nothing in it.
 */
export function span(rows: GanttRow[], now: number): number {
  const near = ahead(rows, now).slice(0, COVERS);
  if (near.length === 0) return STEPS[0];
  return step(finish(near[near.length - 1]) - now);
}

/** Where a bar sits in the window, as fractions of it. */
export interface Slot {
  offset: number;
  width: number;
}

/**
 * Where to draw a bar, or `null` when there is nothing of it in the window.
 *
 * The left edge is *now*, so a bar already running is clipped to it rather than
 * dropped or drawn backwards — which reads correctly as *this has started*, and
 * is why no "now" marker is needed. A bar running past the right edge clips the
 * same way.
 */
export function place(bar: GanttBar, now: number, window: number): Slot | null {
  const from = Math.max(0, (new Date(bar.start).getTime() - now) / window);
  const to = Math.min(1, (finish(bar) - now) / window);
  return to <= from ? null : { offset: from, width: to - from };
}

/**
 * Whether a bar this wide has room for its own name.
 *
 * It falls out of the zoom rule for free: a tight window has fat bars with
 * words in them, a wide window shows colour and shape only — which is all
 * anybody wants about something four hours out.
 */
export function roomy(width: number, cols: number): boolean {
  return width * cols * (1 - NAMES) >= TITLE_CELLS;
}

/** The palette slots a row's bars take when no bar names a colour of its own. */
const SLOTS = 5;

/**
 * A row's own colour, so two bars on one track read as one thing.
 *
 * The board's palette rather than a colour of this widget's invention, so a
 * gantt looks like the charts beside it. A bar that names a colour beats this.
 */
export function tone(row: number): string {
  return `var(--chart-${(row % SLOTS) + 1})`;
}

/**
 * The narrowest two time marks can sit and still both be read, in cells.
 *
 * `04:20` at the size these are drawn is about a cell and a half on this
 * television. Two marks closer than that are one smudge, so the later one comes
 * off rather than being shrunk — the same trade a bar's name makes, and for the
 * same reason: there is no font size at which crowding becomes legible.
 */
export const MARK_CELLS = 1.8;

/** A time written on the axis, and where along the window it falls. */
export interface Mark {
  /** Fraction of the window: 0 at *now*, 1 at its right edge. */
  at: number;
  /** `HH:MM`, the 24-hour form the clock beside it is written in. */
  text: string;
}

const pad = (value: number) => String(value).padStart(2, "0");

/** A time of day with no date on it: the window is one frame, never two. */
function clock(at: number): string {
  const when = new Date(at);
  return `${pad(when.getHours())}:${pad(when.getMinutes())}`;
}

/**
 * The times to write above the bars: where each block starts and ends.
 *
 * Only the edges inside the window. A bar already running started before *now*
 * and one running past the right edge ends after it, and neither instant is on
 * the screen to be labelled — the same clipping `place` does, asked the other
 * way round.
 *
 * Two blocks that meet share an edge and so share one mark rather than printing
 * the same time twice. Past that, a mark that would collide with the one before
 * it is dropped: a crowded axis says less than a sparse one, and the bars
 * underneath still show where every boundary is.
 */
export function marks(
  rows: GanttRow[],
  now: number,
  window: number,
  cols: number,
): Mark[] {
  const edges = new Set<number>();
  for (const row of rows) {
    for (const bar of row.bars) {
      edges.add(new Date(bar.start).getTime());
      edges.add(finish(bar));
    }
  }

  const room = MARK_CELLS / (cols * (1 - NAMES));
  const kept: Mark[] = [];
  for (const at of [...edges].sort((a, b) => a - b)) {
    if (at < now || at > now + window) continue;
    const mark = { at: (at - now) / window, text: clock(at) };
    const last = kept[kept.length - 1];
    if (last === undefined || mark.at - last.at >= room) kept.push(mark);
  }
  return kept;
}
