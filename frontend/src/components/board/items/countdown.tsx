import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { CountdownPayload } from "@/lib/schemas/board";
import { Icon } from "@/components/board/icon";
import { useClock } from "@/hooks/use-clock";
import { useFitting } from "@/hooks/use-fitting";
import { at, ordered, phaseOf, remaining, ticking } from "@/lib/countdown";
import { cn } from "@/lib/utils";

const SECOND = 1000;

/**
 * How long until the next few things.
 *
 * Each row is a title and, under it, the reading and the facts: `02:15 · 14:00
 * – 15:30`. The countdown is the loud half because it is what a glance is for;
 * the times sit dim beside it for whoever walks closer.
 *
 * Which end of the range is bright says which one the clock is counting to —
 * the start while the thing is ahead, the end once it has begun. That is the
 * only signal needed and it costs no words.
 *
 * Nothing writes to this. The datetimes arrive once and the browser counts
 * down, so it keeps working after whoever set it has gone. The order and the
 * dropping-out are worked out here too, on every tick, because both change on
 * their own as the clock passes each start and each end — see `lib/countdown`.
 *
 * Rows are clipped, never scrolled: nobody can scroll this screen. What
 * survives a widget dragged shorter is what is happening, then what is next,
 * which is the whole reason they are ordered.
 */
export function Countdown({
  id,
  payload,
}: {
  id: string;
  payload: CountdownPayload;
}) {
  const { t } = useTranslation();
  // A second only while something is inside its last minute; a slow tick the
  // rest of the time, which is all a clock time ever needs. The cadence follows
  // what is on screen, and is adjusted during the render rather than in an
  // effect — the same answer `widget-wake` gives to state that has to follow
  // what was just worked out.
  const [fast, setFast] = useState(false);
  const now = useClock(fast ? SECOND : undefined);
  const rows = ordered(payload.items, now);
  const soon = ticking(rows, now);
  if (fast !== soon) setFast(soon);
  const { ref, fits } = useFitting(rows.length);

  return (
    <div className="flex size-full flex-col gap-1 overflow-hidden rounded-xl widget-surface widget-edge p-5 widget-text">
      {payload.title ? (
        <h3 className="flex shrink-0 items-center gap-2 text-node font-semibold tracking-tight">
          <Icon name={payload.icon} src={`/api/v1/media/${id}/icon`} />
          {payload.title}
        </h3>
      ) : null}
      {rows.length > 0 ? (
        <ul ref={ref} className="min-h-0 flex-1 overflow-hidden">
          {rows.map((entry, i) => {
            const phase = phaseOf(entry, now);
            const left = remaining(entry, now);
            return (
              <li
                key={`${entry.title}-${entry.start}`}
                className={cn(
                  "flex gap-3 py-2 text-node-sm",
                  // Over, and still there: quiet rather than gone, because
                  // somebody should be able to see what it was.
                  phase === "over" && "opacity-60",
                  // Measured but not drawn — see `useFitting` for why this is
                  // visibility and never display.
                  i >= fits && "invisible",
                )}
              >
                {entry.icon ? (
                  <span className="mt-[0.15em]">
                    <Icon
                      name={entry.icon}
                      src={`/api/v1/media/${id}/icon/${i}`}
                    />
                  </span>
                ) : null}
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{entry.title}</p>
                  <p className="truncate">
                    {left ? (
                      <>
                        <span className="text-node font-semibold">{left}</span>
                        <span className="opacity-40"> · </span>
                      </>
                    ) : null}
                    <span
                      className={
                        phase === "ahead" ? "opacity-75" : "opacity-40"
                      }
                    >
                      {at(entry.start, now)}
                    </span>
                    {entry.end ? (
                      <>
                        <span className="opacity-40"> – </span>
                        <span
                          className={
                            phase === "happening" ? "opacity-75" : "opacity-40"
                          }
                        >
                          {at(entry.end, now)}
                        </span>
                      </>
                    ) : null}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-node-sm opacity-60 italic">
          {payload.empty ?? t("countdown.empty")}
        </p>
      )}
    </div>
  );
}
