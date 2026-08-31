import {
  AlertCircle,
  AlertTriangle,
  Bell,
  Bug,
  Check,
  Clock,
  Cpu,
  Download,
  Flame,
  GitBranch,
  HardDrive,
  Info,
  Mail,
  MessageSquare,
  Rocket,
  Terminal,
  Upload,
  Wrench,
  XCircle,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { Notification } from "@/lib/schemas/board";

// A closed set, named the same on both sides. Importing every lucide icon to
// support names nobody picks would cost the whole library in the bundle.
const NAMED: Record<string, LucideIcon> = {
  bell: Bell,
  check: Check,
  info: Info,
  "alert-triangle": AlertTriangle,
  "alert-circle": AlertCircle,
  "x-circle": XCircle,
  terminal: Terminal,
  "git-branch": GitBranch,
  download: Download,
  upload: Upload,
  cpu: Cpu,
  "hard-drive": HardDrive,
  mail: Mail,
  "message-square": MessageSquare,
  clock: Clock,
  zap: Zap,
  flame: Flame,
  bug: Bug,
  rocket: Rocket,
  wrench: Wrench,
};

/** What a notification's level looks like, when it has no icon of its own. */
const FALLBACK: Record<Notification["level"], LucideIcon> = {
  info: Info,
  success: Check,
  warn: AlertTriangle,
  error: XCircle,
};

/**
 * A notification's icon: a named one, an image it points at, or its level.
 *
 * An image is served by id rather than by path, the same way item media is, so
 * a filesystem path never reaches a URL.
 */
export function NotificationIcon({
  notification,
}: {
  notification: Notification;
}) {
  const { icon, level, id } = notification;

  if (icon?.startsWith("/")) {
    return (
      <img
        src={`/api/v1/notifications/${id}/icon`}
        alt=""
        className="size-[1.4em] shrink-0 rounded object-cover"
      />
    );
  }

  const Glyph = (icon && NAMED[icon]) || FALLBACK[level];
  return <Glyph className="size-[1.2em] shrink-0" />;
}
