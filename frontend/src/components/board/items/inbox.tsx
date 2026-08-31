import { useTranslation } from "react-i18next";
import type { InboxPayload, Notification } from "@/lib/schemas/board";
import { NotificationIcon } from "@/components/board/notification-icon";
import { useClock } from "@/hooks/use-clock";

const LEVEL_TINT: Record<Notification["level"], string> = {
  info: "text-info",
  success: "text-success",
  warn: "text-warning",
  error: "text-destructive",
};

/**
 * The clock time it happened, or "now" while that is still this minute.
 *
 * Absolute rather than an age, because an age has to be recomputed to stay
 * true and a wall display is mostly not being re-rendered.
 */
function when(iso: string, justNow: string): string {
  const at = new Date(iso);
  // h23 rather than the browser's preference: chart axes on this board are
  // 24-hour, and two clock conventions on one screen is worse than either.
  const clock = at.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const now = new Date();
  const sameMinute =
    at.getHours() === now.getHours() && at.getMinutes() === now.getMinutes();
  return sameMinute ? justNow : clock;
}

function Row({ notification }: { notification: Notification }) {
  const { t } = useTranslation();
  return (
    <li className="flex gap-3 py-2 text-node-sm">
      <span className={`mt-[0.15em] ${LEVEL_TINT[notification.level]}`}>
        <NotificationIcon notification={notification} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2 opacity-60">
          <span className="truncate">{notification.source ?? "—"}</span>
          <span className="shrink-0">
            {when(notification.created_at, t("inbox.justNow"))}
          </span>
        </div>
        <p className="truncate font-semibold">{notification.title}</p>
        {notification.body ? (
          <p className="line-clamp-2 opacity-75">{notification.body}</p>
        ) : null}
      </div>
    </li>
  );
}

/**
 * The notification shade.
 *
 * How many fit is decided by how tall the tile is and how much of each line
 * fits by how wide — neither is configured, they are just what the size does.
 * Overflow is clipped rather than scrolled: the newest are at the top, and
 * nobody can scroll this screen anyway.
 */
export function Inbox({
  payload,
  notifications,
}: {
  payload: InboxPayload;
  notifications: Notification[];
}) {
  const { t } = useTranslation();
  // So "now" turns into a clock time when its minute passes, instead of
  // outliving it until something else on the board changes.
  useClock();

  return (
    <div className="flex size-full flex-col gap-1 overflow-hidden rounded-xl tile-surface p-5 tile-text">
      {payload.title ? (
        <h3 className="shrink-0 text-node font-semibold tracking-tight">
          {payload.title}
        </h3>
      ) : null}
      {notifications.length > 0 ? (
        <ul className="min-h-0 flex-1 divide-y divide-current/10 overflow-hidden">
          {notifications.map((notification) => (
            <Row key={notification.id} notification={notification} />
          ))}
        </ul>
      ) : (
        <p className="text-node-sm opacity-60 italic">{t("inbox.empty")}</p>
      )}
    </div>
  );
}
