import type { NotificationPayload } from "@/lib/schemas/board";
import { ScrollingText } from "@/components/board/scrolling-text";

/**
 * An announcement. It stays until dismissed, so several finished sessions can
 * pile up and be read in one glance.
 *
 * The level shows as the colour of the tile, which the grid applies — it used
 * to be a thick bar down the left edge, and borders are gone everywhere.
 */
export function Notification({ payload }: { payload: NotificationPayload }) {
  return (
    <div className="flex size-full flex-col justify-center rounded-xl tile-surface px-5 py-3 text-foreground">
      <ScrollingText text={payload.message} className="text-node" />
      {payload.source ? (
        <span className="mt-1 text-node-sm text-muted-foreground">
          {payload.source}
        </span>
      ) : null}
    </div>
  );
}
