import {
  AlertTriangle,
  Check,
  Info,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { InboxPayload, Notification } from "@/lib/schemas/board";
import { EntryRow } from "@/components/board/entry-row";
import { Icon } from "@/components/board/icon";
import { useClock } from "@/hooks/use-clock";

const LEVEL_TINT: Record<Notification["level"], string> = {
  info: "text-info",
  success: "text-success",
  warn: "text-warning",
  error: "text-destructive",
};

/** What a level looks like when the notification brought no icon of its own. */
const LEVEL_GLYPH: Record<Notification["level"], LucideIcon> = {
  info: Info,
  success: Check,
  warn: AlertTriangle,
  error: XCircle,
};

// The default for an entry's text, whatever colour the widget itself is: an
// inbox is read line by line, and a line that has to stand out says so for
// itself.
const DEFAULT_TEXT = "#fff";

/**
 * The notification shade.
 *
 * How many fit is decided by how tall the widget is and how much of each line
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
    <div className="flex size-full flex-col gap-1 overflow-hidden rounded-xl widget-surface p-5 widget-text">
      {payload.title ? (
        <h3 className="shrink-0 text-node font-semibold tracking-tight">
          {payload.title}
        </h3>
      ) : null}
      {notifications.length > 0 ? (
        <ul className="min-h-0 flex-1 divide-y divide-current/10 overflow-hidden">
          {notifications.map((notification) => (
            <EntryRow
              key={notification.id}
              icon={
                <Icon
                  name={notification.icon}
                  src={`/api/v1/notifications/${notification.id}/icon`}
                  fallback={LEVEL_GLYPH[notification.level]}
                  className={LEVEL_TINT[notification.level]}
                />
              }
              source={notification.source}
              at={notification.created_at}
              title={notification.title}
              titleColor={notification.title_color ?? DEFAULT_TEXT}
              body={notification.body}
              bodyColor={notification.body_color ?? DEFAULT_TEXT}
            />
          ))}
        </ul>
      ) : (
        <p className="text-node-sm opacity-60 italic">{t("inbox.empty")}</p>
      )}
    </div>
  );
}
