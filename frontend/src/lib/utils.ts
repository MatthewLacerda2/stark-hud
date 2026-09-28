import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * Every font size `styles.css` defines, as `text-<name>`, and nothing else.
 *
 * tailwind-merge only knows Tailwind's own scale (`text-sm`, `text-lg`…). Told
 * nothing, it reads `text-h3` as a colour — the only other thing `text-<word>`
 * can be — and `cn("text-h3 text-foreground")` keeps the colour and drops the
 * size. Named here, a size and a colour are two groups and both survive, while
 * two sizes still resolve last-wins.
 *
 * A list rather than something read from the stylesheet at runtime: that would
 * ship the whole stylesheet into the bundle a second time, as a string, to
 * parse on every page load. `utils.test.ts` compares this list with the
 * `--text-*` names in `styles.css`, so a token added there and not here fails
 * a gate instead of quietly losing its size beside a colour.
 */
export const FONT_SIZES = [
  "node-sm",
  "node",
  "node-lg",
  "node-xl",
  "gauge-label",
  "gauge-label-alone",
  "gauge-reading",
  "gauge-mark",
  "origin",
  "chart-mark",
  "progress",
  "progress-mark",
  "display",
  "h1",
  "h2",
  "h3",
  "body",
  "caption",
  "kpi-lg",
  "kpi-sm",
] as const;

const twMerge = extendTailwindMerge({
  extend: { classGroups: { "font-size": [{ text: [...FONT_SIZES] }] } },
});

/** Merge class names, resolving conflicting Tailwind utilities last-wins. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
