import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { initials, monthOf } from "@/lib/calendar";
import { cn } from "@/lib/utils";

// A calendar is only ever wrong about one thing and it goes wrong at midnight,
// so once a minute catches it and costs a sixtieth of what the clock beside it
// spends being right to the second.
const TICK_MS = 60_000;

// The box around today, drawn in the ink the rest of the widget is written in
// so that `set_ink` takes it along instead of leaving a white ring behind on a
// recoloured board. Sized in `em` because it is a box around a number and has
// to grow with the number, not with the screen.
const TODAY = {
  border: "0.09em solid currentColor",
  borderRadius: "0.3em",
} as const;

/**
 * This month, with today in a box.
 *
 * It reads the browser's clock, like the clock widget and for the same reason:
 * one fed over the socket would be wrong at midnight and stale by the morning,
 * and this has to be right at 4am with nothing else running.
 *
 * No month name. Whoever is looking already knows what month it is — that is
 * the difference between a board and a form — and a header band costs its full
 * height whether or not the widget has any to spare.
 *
 * Only today is marked, and every other day is a bare number. One box on the
 * whole widget is what makes it the thing your eye lands on from the sofa; a
 * grid where several days are decorated is a grid you have to read.
 */
export function Calendar() {
  const { i18n } = useTranslation();
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), TICK_MS);
    return () => clearInterval(id);
  }, []);

  const { days, weeks } = monthOf(now);
  const today = now.getDate();

  return (
    <div className="flex size-full flex-col gap-[3cqmin] rounded-xl widget-surface widget-edge p-[5cqmin] widget-text">
      <div className="grid grid-cols-7 text-node-sm font-semibold opacity-50">
        {initials(i18n.language).map((letter, at) => (
          <span key={at} className="text-center">
            {letter}
          </span>
        ))}
      </div>
      <div
        className="grid min-h-0 flex-1 grid-cols-7 text-node tabular-nums"
        style={{ gridTemplateRows: `repeat(${weeks}, minmax(0, 1fr))` }}
      >
        {days.map((day, at) => (
          <span
            key={at}
            className={cn(
              "flex items-center justify-center",
              day === today ? "font-bold" : "opacity-65",
            )}
          >
            {day === null ? null : (
              // A minimum width so the 1st gets the same box as the 28th:
              // `aspect-square` alone would size it to the digits inside.
              <span
                className="flex aspect-square min-w-[1.7em] items-center justify-center"
                style={day === today ? TODAY : undefined}
              >
                {day}
              </span>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}
