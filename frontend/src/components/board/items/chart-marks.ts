import type { ChartThreshold } from "@/lib/schemas/board";
import type { ChartConfig } from "@/components/ui/chart";

/**
 * What a chart and its gauge have to agree about a mark: what colour it is, and
 * how long it takes to get somewhere.
 *
 * Here rather than in `chart.tsx` because the gauge lives in its own file and
 * asks the same questions the cartesian charts do — which colour is this
 * series, has this value gone past a line, what does shadcn want to be told,
 * how fast does a reading land. Two copies of that would be two charts that
 * disagree about red, or about a second.
 */

/**
 * How long a mark takes to reach a new reading, in milliseconds.
 *
 * Two charts move: the gauge's ring, and the radar's polygon. They are the
 * board's pulse — a ring that only ever cuts to a new angle reads as a picture
 * of a dashboard rather than a dashboard — so they still move, and the argument
 * beside the radar for why it breathes is still true at this length.
 *
 * What it trades is the length of the breath. Recharts' own default is 1500 ms,
 * which nobody here chose: the gauge had it because it is the library's default
 * and the radar because its animation was asked for without a duration. At
 * 1500 ms of every 3000 ms between readings, half of all time was a mark in
 * motion — and on this board a mark in motion is redrawn every frame and then
 * multiplied by the eight copies behind it (`extrusion.tsx`), which came to
 * most of what the whole board cost. A fifth of that duration is a movement you
 * can still see and a tenth of the bill.
 *
 * Line and area charts do not take it. They carry history rather than a
 * reading, so a new sample slides the window and tweening it morphs the whole
 * shape; that is decided beside them, and it has not changed.
 */
export const SWEEP_MS = 300;

/** How many default colours the theme carries before they start repeating. */
const SLOTS = 5;

/** The colour for series `i`: whatever was asked for, else the next default. */
export function pick(colors: string[], i: number): string {
  return colors.length > 0
    ? colors[i % colors.length]
    : `var(--chart-${(i % SLOTS) + 1})`;
}

/**
 * The colour a value has earned by going past a line, or null if it has not.
 *
 * Every chart here is one tone, so a mark that turns is saying something rather
 * than being decorated. The highest threshold the value clears wins — that way
 * an attention level and an alarm level can be given in either order and the
 * alarm still shows when both are past.
 */
export function crossed(marks: ChartThreshold[], value: number): string | null {
  let hit: ChartThreshold | null = null;
  for (const mark of marks) {
    if (value > mark.at && (hit === null || mark.at > hit.at)) hit = mark;
  }
  return hit?.color ?? null;
}

/** Map each series onto a colour, the way shadcn's ChartConfig expects. */
export function toConfig(series: string[], colors: string[]): ChartConfig {
  return Object.fromEntries(
    series.map((key, i) => [key, { label: key, color: pick(colors, i) }]),
  );
}
