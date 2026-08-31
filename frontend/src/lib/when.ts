/**
 * The clock time something happened, or "now" while that is still this minute.
 *
 * Absolute rather than an age, because an age has to be recomputed to stay true
 * and a wall display is mostly not being re-rendered.
 *
 * Shared by the inbox and the feed: they are the same line, and two ways of
 * writing a time on one screen is worse than either.
 */
export function when(iso: string, justNow: string): string {
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
