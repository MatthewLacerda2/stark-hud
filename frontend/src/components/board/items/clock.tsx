import { useEffect, useState } from "react";

const pad = (n: number) => String(n).padStart(2, "0");

// Below this the widget has no room for a second line, so the date is dropped
// rather than shrunk into something nobody can read from the sofa.
const ROWS_FOR_DATE = 2;

/**
 * The time now, with the date under it.
 *
 * It reads the browser's clock every second instead of being fed over the
 * socket: a clock that depends on a writer stops when the writer does, and this
 * one has to be right at 4am with nothing else running.
 *
 * Digits are tabular so the widget does not twitch as the seconds change width,
 * and set in a rounded face — a clock is the one widget nobody reads, only
 * glances at, so it can afford to look like an object rather than like text.
 */
export function Clock({ rows }: { rows: number }) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const time = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  const date = `${pad(now.getDate())}/${pad(now.getMonth() + 1)}/${String(
    now.getFullYear(),
  ).slice(-2)}`;

  return (
    <div className="flex size-full flex-col items-center justify-center gap-1 rounded-xl widget-surface widget-edge p-4 font-rounded widget-text">
      <span className="text-node-xl font-bold tabular-nums tracking-tight">
        {time}
      </span>
      {rows >= ROWS_FOR_DATE ? (
        <span
          className="font-semibold tabular-nums opacity-70"
          // Half again the small size: the date is a caption, but a caption on
          // a TV still has to be legible from the sofa.
          style={{ fontSize: "calc(var(--text-node-sm) * 1.5)" }}
        >
          {date}
        </span>
      ) : null}
    </div>
  );
}
