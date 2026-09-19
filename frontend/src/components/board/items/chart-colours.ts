import type { ChartThreshold } from "@/lib/schemas/board";
import type { ChartConfig } from "@/components/ui/chart";

/**
 * What decides the colour of a mark, shared by every chart that draws one.
 *
 * Here rather than in `chart.tsx` because the gauge lives in its own file and
 * asks the same three questions the cartesian charts do: which colour is this
 * series, has this value gone past a line, and what does shadcn want to be
 * told. Two copies of that would be two charts that disagree about red.
 */

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
