/**
 * What a progress bar shows, mirroring `backend/schemas/progress.py`.
 *
 * Its own module because `board.ts` is at the house's 550-line ceiling.
 * `board.ts` re-exports it, so nothing has to know.
 */

import type { IconRef } from "@/lib/schemas/board";

/** Which end of the bar the icon sits at. */
export type IconSide = "start" | "end";

/**
 * One number between two others, drawn as a bar filling up.
 *
 * The ends name where the bar is going, not where it is: the far end draws
 * `max`, the near end `min` only when it is not zero. A label replaces either
 * number with text, and an empty one hides it.
 */
export interface ProgressPayload {
  kind: "progress";
  value: number;
  min: number;
  max: number;
  title: string | null;
  icon: IconRef | null;
  icon_side: IconSide;
  /** Null draws the number; an empty string draws nothing. */
  min_label: string | null;
  max_label: string | null;
  /** The filled part. Null takes the gauges' translucent white. */
  color: string | null;
  /** The part not reached yet. Null takes a fainter white. */
  unfilled: string | null;
}
