/**
 * The two readings a progress bar takes off its payload: how much of the bar is
 * filled, and what each end says. Kept out of the component so they can be
 * tested as sums rather than read back off the page.
 */
import type { ProgressPayload } from "@/lib/schemas/board";

/** How far along `value` is between the two ends, as a percentage of the bar. */
export function filled(payload: ProgressPayload): number {
  const share = (payload.value - payload.min) / (payload.max - payload.min);
  return Math.min(100, Math.max(0, share * 100));
}

/**
 * What an end of the bar says: its own text if it was given one, else the
 * number — except a near end at zero, which a bar starting from nothing does
 * not need to say. An empty label is how a caller hides an end on purpose.
 */
export function endLabel(
  label: string | null,
  number: number,
  near: boolean,
  locale: string,
): string {
  if (label !== null) return label;
  if (near && number === 0) return "";
  return new Intl.NumberFormat(locale, {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(number);
}
