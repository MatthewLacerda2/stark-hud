import type { NotificationPayload } from "@/lib/schemas/board";
import { ScrollingText } from "@/components/board/scrolling-text";

// The level is the colour of the tile itself now. It used to be a thick bar
// down the left edge, which was a border, and borders are gone everywhere.
const TONE: Record<NotificationPayload["level"], string> = {
  info: "var(--color-info)",
  success: "var(--color-success)",
  warn: "var(--color-warning)",
  error: "var(--color-destructive)",
};

/**
 * An announcement. It stays until dismissed, so several finished sessions can
 * pile up and be read in one glance.
 */
export function Notification({ payload }: { payload: NotificationPayload }) {
  return (
    <div
      className="flex size-full flex-col justify-center rounded-xl tile-surface px-5 py-3 text-foreground"
      style={{ "--tile-colour": TONE[payload.level] } as React.CSSProperties}
    >
      <ScrollingText text={payload.message} className="text-node" />
      {payload.source ? (
        <span className="mt-1 text-node-sm text-muted-foreground">
          {payload.source}
        </span>
      ) : null}
    </div>
  );
}
