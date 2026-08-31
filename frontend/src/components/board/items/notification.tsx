import type { NotificationPayload } from "@/lib/schemas/board";
import { ScrollingText } from "@/components/board/scrolling-text";

const TONES: Record<NotificationPayload["level"], string> = {
  info: "border-info bg-info/10",
  success: "border-success bg-success/10",
  warn: "border-warning bg-warning/10",
  error: "border-destructive bg-destructive/10",
};

/**
 * An announcement. It stays until dismissed, so several finished sessions can
 * pile up and be read in one glance.
 */
export function Notification({ payload }: { payload: NotificationPayload }) {
  return (
    <div
      className={`flex size-full flex-col justify-center rounded-xl border-l-8 px-5 py-3 text-foreground ${TONES[payload.level]}`}
    >
      <ScrollingText text={payload.message} className="text-node" />
      {payload.source ? (
        <span className="mt-1 text-caption text-muted-foreground">
          {payload.source}
        </span>
      ) : null}
    </div>
  );
}
