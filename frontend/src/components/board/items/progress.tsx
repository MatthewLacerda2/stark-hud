import { useTranslation } from "react-i18next";
import type { ProgressPayload } from "@/lib/schemas/board";
import { Icon } from "@/components/board/icon";
import { endLabel, filled } from "@/lib/progress";

// The same translucent white the gauges draw with, filled and unfilled, so a
// bar beside a row of gauges reads as one more of them rather than as a guest.
const FILLED = "#ffffffa6";
const UNFILLED = "#ffffff40";

// `cqmin` needs a container sized in both axes, which the widget's own
// `@container` is not — the gauge declares one of its own for the same reason.
const SIZED = { containerType: "size" } as const;

// A reading moving is the bar settling somewhere else, so it takes the board's
// own motion for that rather than an easing of its own.
const SETTLE = {
  transition: "width var(--motion-settle) var(--motion-settle-ease)",
} as const;

/**
 * How far along something is: a gauge laid flat.
 *
 * One line of type with a bar in it — the icon at one end, the numbers either
 * side of the bar, the title over it. Every part is optional, and whatever is
 * missing gives its room to the bar: with no title the bar takes the widget's
 * height, with no labels its width. The bar itself is never missing.
 *
 * The value is not written anywhere. The fill is the reading; a number beside
 * it would be the same thing said twice, which is the argument the gauge made
 * first.
 */
export function Progress({
  id,
  payload,
}: {
  id: string;
  payload: ProgressPayload;
}) {
  const { i18n } = useTranslation();
  const near = endLabel(payload.min_label, payload.min, true, i18n.language);
  const far = endLabel(payload.max_label, payload.max, false, i18n.language);
  const icon = payload.icon ? (
    <span className="flex shrink-0 text-progress-mark">
      <Icon name={payload.icon} src={`/api/v1/media/${id}/icon`} />
    </span>
  ) : null;

  return (
    <div
      className="flex size-full items-center gap-[6cqmin] overflow-hidden rounded-xl widget-surface widget-edge p-[6cqmin] widget-text"
      style={SIZED}
    >
      {payload.icon_side === "start" ? icon : null}
      <div className="flex h-full min-w-0 flex-1 flex-col gap-[4cqmin] text-progress">
        {/* The title gives way before the bar does: squashed flat, the widget
            clips its title and keeps at least half its height for the bar,
            because a progress bar with no bar is a label. */}
        {payload.title ? (
          <span className="min-h-0 shrink truncate font-semibold">
            {payload.title}
          </span>
        ) : null}
        <div className="flex flex-[1_0_50%] items-center gap-[6cqmin] font-semibold tabular-nums">
          {near ? <span className="shrink-0">{near}</span> : null}
          <div
            className="relative h-full min-w-0 flex-1 overflow-hidden rounded-full"
            data-extrude-mark
            style={{ backgroundColor: payload.unfilled ?? UNFILLED }}
          >
            <div
              data-testid="progress-fill"
              className="h-full rounded-full"
              style={{
                ...SETTLE,
                width: `${filled(payload)}%`,
                backgroundColor: payload.color ?? FILLED,
              }}
            />
          </div>
          {far ? <span className="shrink-0">{far}</span> : null}
        </div>
      </div>
      {payload.icon_side === "end" ? icon : null}
    </div>
  );
}
