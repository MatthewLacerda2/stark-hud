import { useTranslation } from "react-i18next";
import type { GanttBar, GanttPayload } from "@/lib/schemas/board";
import { Icon } from "@/components/board/icon";
import { useClock } from "@/hooks/use-clock";
import { useFitting } from "@/hooks/use-fitting";
import { carriesAlpha } from "@/lib/colour";
import { NAMES, label, place, roomy, span, tone } from "@/lib/gantt";
import { cn } from "@/lib/utils";

/**
 * How solid a bar is when its colour did not say.
 *
 * A block rather than a tint — a bar has to read as an object from across the
 * room — but not solid, because the board sits on a video and the whole look of
 * it is that the video keeps moving underneath. A colour that states its own
 * alpha has already answered this and is drawn as written.
 */
const WASH = 0.35;

/**
 * The next stretch of time, as named rows of bars.
 *
 * This is the widget for two things happening at once. A countdown says *when*
 * one thing is, and a reading has no width; here width is duration, so what is
 * running, what is next and what overlaps is readable without reading a word.
 *
 * Nothing writes to it. The instants arrive once and the browser works out the
 * geometry on every tick, so an evening dictated at 18:00 plays itself out
 * until midnight — including the scale, which is the smallest step covering the
 * next few bars and re-tunes itself as the clock passes each of them. That is
 * also why the span is stated in the corner: width means nothing without the
 * frame it is drawn in, and a scale that changed silently would make the same
 * task look like a different amount of work between two glances.
 *
 * The left edge is *now*, so there is no marker for it and nothing behind it is
 * drawn: a bar already running is clipped to that edge, which reads correctly
 * as *this has started*. A bar says its own name when it is wide enough to hold
 * one and shows only colour and place when it is not, which is all anybody
 * wants about something four hours out.
 *
 * Rows are clipped, never scrolled: nobody can scroll this screen.
 */
export function Gantt({
  id,
  payload,
  cols,
}: {
  id: string;
  payload: GanttPayload;
  /** How many cells wide the widget is. It decides which bars can hold a word. */
  cols: number;
}) {
  const { t } = useTranslation();
  // The slow tick. A bar's edge moves by a hundredth of an hour-wide window in
  // half a minute, and nothing here ever counts seconds.
  const now = useClock();
  const window = span(payload.rows, now);
  // A row with nothing ahead of it is history, and this widget draws none.
  // Kept whole rather than by what is in the window, so a row does not blink
  // out and back as the scale re-tunes around it.
  const rows = payload.rows.filter((row) =>
    row.bars.some((bar) => new Date(bar.end).getTime() > now),
  );
  const { ref, fits } = useFitting(rows.length);

  return (
    <div className="flex size-full flex-col gap-1 overflow-hidden rounded-xl widget-surface widget-edge p-5 widget-text">
      {rows.length > 0 || payload.title ? (
        <div className="flex shrink-0 items-baseline gap-2">
          <h3 className="flex min-w-0 flex-1 items-center gap-2 truncate text-node font-semibold tracking-tight">
            <Icon name={payload.icon} src={`/api/v1/media/${id}/icon`} />
            {payload.title}
          </h3>
          {rows.length > 0 ? (
            <span className="shrink-0 text-node-sm opacity-50">
              {label(window)}
            </span>
          ) : null}
        </div>
      ) : null}
      {rows.length > 0 ? (
        <ul ref={ref} className="min-h-0 flex-1 overflow-hidden">
          {rows.map((row, i) => (
            <li
              key={row.name}
              className={cn(
                "flex items-stretch gap-2 py-1 text-node-sm",
                // Measured but not drawn — see `useFitting` for why this is
                // visibility and never display.
                i >= fits && "invisible",
              )}
            >
              <span
                className="shrink-0 truncate opacity-60"
                style={{ width: `${NAMES * 100}%` }}
              >
                {row.name}
              </span>
              <div className="relative min-w-0 flex-1">
                {row.bars.map((bar) => (
                  <Bar
                    key={`${bar.title}-${bar.start}`}
                    bar={bar}
                    now={now}
                    window={window}
                    cols={cols}
                    fallback={tone(i)}
                  />
                ))}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-node-sm opacity-60 italic">
          {payload.empty ?? t("gantt.empty")}
        </p>
      )}
    </div>
  );
}

/** One bar in its row, or nothing when none of it falls inside the window. */
function Bar({
  bar,
  now,
  window,
  cols,
  fallback,
}: {
  bar: GanttBar;
  now: number;
  window: number;
  cols: number;
  fallback: string;
}) {
  const slot = place(bar, now, window);
  if (slot === null) return null;
  const colour = bar.color ?? fallback;

  return (
    <div
      className="absolute inset-y-0 flex items-center overflow-hidden rounded-sm px-2"
      style={{ left: `${slot.offset * 100}%`, width: `${slot.width * 100}%` }}
    >
      {/* The colour is its own layer so that turning it down does not take the
          name down with it. `opacity` on the bar itself would fade both. */}
      <div
        className="absolute inset-0"
        style={{
          background: colour,
          opacity: carriesAlpha(colour) ? 1 : WASH,
        }}
      />
      {roomy(slot.width, cols) ? (
        <span className="relative truncate">{bar.title}</span>
      ) : null}
    </div>
  );
}
