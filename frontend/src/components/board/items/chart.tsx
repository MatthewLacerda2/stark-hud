import { useTranslation } from "react-i18next";
import {
  Area,
  AreaChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  Bar,
  BarChart,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartPayload, ChartThreshold } from "@/lib/schemas/board";
import { ChartContainer, type ChartConfig } from "@/components/ui/chart";
import { Card, CardContent } from "@/components/ui/card";
import { Icon } from "@/components/board/icon";
import { cn } from "@/lib/utils";

const SLOTS = 5;

// No tooltip and no legend anywhere in here. A tooltip needs a pointer and the
// screen this is drawn on has none; a legend is a second thing to read on a
// chart meant to be understood without reading. What a series is belongs in the
// widget's own title, or in the icon beside it.

// Recharts paints axis labels with SVG `fill`, which the widget's `color` never
// reaches. Handed to them by name instead, with shadcn's own muted-foreground as
// the fallback so a chart nobody coloured looks exactly as it did. Passed as a
// class rather than a prop because the container styles those labels with one of
// its own, and a class is what replaces a class.
const AXIS_INK =
  "[&_.recharts-cartesian-axis-tick-value]:fill-[var(--widget-text,var(--color-muted-foreground))]";

/** The colour for series `i`: whatever was asked for, else the next default. */
function pick(colors: string[], i: number): string {
  return colors.length > 0
    ? colors[i % colors.length]
    : `var(--chart-${(i % SLOTS) + 1})`;
}

/**
 * The colour a value has earned by going past a line, or null if it has not.
 *
 * Every chart here is one tone, so a mark that turns is saying something rather
 * than being decorated. The highest threshold the value clears wins — that way
 * an attention level and an alarm level can be given in either order and the
 * alarm still shows when both are past.
 */
function crossed(marks: ChartThreshold[], value: number): string | null {
  let hit: ChartThreshold | null = null;
  for (const mark of marks) {
    if (value > mark.at && (hit === null || mark.at > hit.at)) hit = mark;
  }
  return hit?.color ?? null;
}

/** True when a colour states its own alpha, as `#rgba` or `#rrggbbaa` do. */
function carriesAlpha(color: string): boolean {
  return /^#(?:[0-9a-f]{4}|[0-9a-f]{8})$/i.test(color);
}

/** Map each series onto a colour, the way shadcn's ChartConfig expects. */
function toConfig(series: string[], colors: string[]): ChartConfig {
  return Object.fromEntries(
    series.map((key, i) => [key, { label: key, color: pick(colors, i) }]),
  );
}

// The part of the ring the value has not reached: white, kept see-through so the
// video still moves behind it. Solid white would glare on a television in a dim
// room and compete with the mark sitting inside the ring. Every widget here sits
// on the same dark video, so there is nothing for this to vary with.
const UNFILLED = "#ffffff40";

// The middle of the ring is a circle, and what goes in it has to fit a square
// inside that circle — 72% of the shorter side across, so about half of it on a
// side. `cqmin` needs a container sized in both axes, which the widget's own
// `@container` is not, so the gauge declares one of its own.
const SIZED = { containerType: "size" } as const;
const HOLE = "flex size-[50cqmin] flex-col justify-center overflow-hidden";

/**
 * A gauge: one number, drawn as a ring, with what it is about inside it.
 *
 * The ring is a whole circle and always was — the value decides how far round
 * the bar goes, not how much circle there is, so the track behind it can close
 * the loop and the reading is a proportion you can see from the sofa.
 *
 * The middle says who the gauge is rather than repeating what the ring already
 * shows: an icon, a short label, and under them whatever the row's `x_key`
 * spelled out — "3.7 de 15.6 GB", which is the sentence its collector wrote and
 * not a number we round. Any of the three may be missing; the value never is.
 *
 * With an icon the two of them are a pair, aligned from the left so they read as
 * one thing and a long label runs out to the right instead of shoving the icon
 * about. With no icon there is nothing to pair with, so the label is centred in
 * the hole like the number used to be.
 */
function Gauge({ id, payload }: { id: string; payload: ChartPayload }) {
  const row = payload.data[0];
  const ceiling = payload.max ?? 100;
  // Left alignment exists so an icon and a label read as one unit from the same
  // edge. On its own, either of them is just a thing in the middle of a ring,
  // and pushing it left only looks like a mistake.
  const paired = Boolean(payload.icon && payload.title);
  const reading = String(row[payload.x_key] ?? "");
  // A gauge has one value, so that value alone decides whether the ring is
  // still the board's white or has turned into a warning.
  const arc =
    crossed(payload.thresholds, Number(row[payload.series[0]])) ??
    pick(payload.colors, 0);

  return (
    <div className="relative size-full" style={SIZED}>
      <ChartContainer
        config={toConfig(payload.series, payload.colors)}
        className="size-full"
      >
        <RadialBarChart
          data={[row]}
          // The whole circle, with the axis below deciding where the bar stops.
          // Made the arc's own extent, the track had only the bar's sweep to
          // paint and the rest of the ring did not exist.
          startAngle={90}
          endAngle={-270}
          innerRadius="72%"
          outerRadius="100%"
          // The arc is the whole widget, so it gets the whole widget. Recharts
          // otherwise keeps five pixels of margin all round and shaves a tenth
          // off the ring for the gap between bars, which is a gap between one
          // bar and itself. Both come back as radius.
          margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
          barCategoryGap={0}
        >
          <PolarAngleAxis
            type="number"
            domain={[0, ceiling]}
            tick={false}
            axisLine={false}
          />
          <RadialBar
            dataKey={payload.series[0]}
            // An inline style, not the `fill` attribute it looks like it should
            // be. ChartContainer ships shadcn's
            // `[&_.recharts-radial-bar-background-sector]:fill-muted`, and any
            // CSS declaration beats an SVG presentation attribute — so the
            // attribute form was overwritten with the muted grey every time, and
            // no value passed here had ever reached the screen. A style wins.
            background={{ style: { fill: payload.unfilled ?? UNFILLED } }}
            cornerRadius={999}
            fill={arc}
          />
        </RadialBarChart>
      </ChartContainer>
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div className={cn(HOLE, paired ? "items-start" : "items-center")}>
          {payload.icon || payload.title ? (
            <span
              className={cn(
                "flex w-full min-w-0 items-center gap-[0.3em] widget-text",
                // Alone in the ring, the word takes the room the icon would
                // have had. Beside one it is sized to sit next to something.
                payload.icon ? "text-gauge-label" : "text-gauge-label-alone",
                paired ? "justify-start" : "justify-center",
              )}
            >
              {payload.icon ? (
                <span
                  className={cn(
                    "flex shrink-0",
                    // Beside a label the mark matches it; alone it is measured
                    // against the ring instead, so it keeps its share of the
                    // circle at every size the widget is dragged to.
                    payload.title ? undefined : "text-gauge-mark",
                  )}
                >
                  <Icon name={payload.icon} src={`/api/v1/media/${id}/icon`} />
                </span>
              ) : null}
              {payload.title ? (
                <span className="truncate">{payload.title}</span>
              ) : null}
            </span>
          ) : null}
          {reading ? (
            <span
              className={cn(
                "w-full truncate text-gauge-reading text-muted-foreground",
                paired ? "text-left" : "text-center",
              )}
            >
              {reading}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/**
 * What the chart is, drawn in the top-left corner: the icon, and the title
 * under it.
 *
 * It used to sit at the origin, on the argument that the corner where the axes
 * meet is space the plot already reserves. True, and it stopped being the point
 * once most charts on this board turned their axes off: with no axes there is
 * no origin, only four corners, and the top-left is where a chart has been
 * labelled since before any of this. It is also where the eye starts.
 *
 * A gauge does not have one, and never did want one. It draws its own inside
 * its ring — see `Gauge` — for the reason this exists at all: "a ring given the
 * corner as well is a bigger ring".
 *
 * **Anchored** is the operative word, and the half that has not changed. The
 * box is pinned by its top edge and sits outside the vertical flow entirely, so
 * a longer title grows *downward* into space the plot is already drawing
 * through, and never pushes the plot anywhere. A chart with a short title costs
 * no height for it, and one with a long title costs height only where the words
 * actually are.
 *
 * A title long enough to reach into the plot overlaps it rather than being
 * clipped or given a box of its own. On a dark board that reads correctly — it
 * is a label over the marks, not a box — and clipping would lose words a caller
 * meant to say. It is held to a share of the width so it wraps rather than
 * running the length of the chart.
 *
 * The one thing this costs: on a chart that *does* draw a y axis, the mark now
 * shares the corner with the topmost tick label rather than sitting under the
 * baseline where nothing was. Worth knowing; not worth two rules.
 *
 * Both parts are optional and all four combinations mean something — nothing at
 * all for the slimmest a chart gets, an icon alone for the CPU strip, a title
 * alone where the header band used to be, or the two of them stacked as one
 * thing. That is the rule the gauge already keeps for its middle.
 */
function Corner({ id, payload }: { id: string; payload: ChartPayload }) {
  if (!payload.icon && !payload.title) return null;
  return (
    <div className="pointer-events-none absolute top-0 left-0 flex max-w-[70%] flex-col items-start gap-[0.25em] text-chart-mark widget-text">
      {payload.icon ? (
        <span className="flex">
          <Icon name={payload.icon} src={`/api/v1/media/${id}/icon`} />
        </span>
      ) : null}
      {payload.title ? (
        <span className="text-node-sm">{payload.title}</span>
      ) : null}
    </div>
  );
}

function Body({ payload }: { payload: ChartPayload }) {
  const { data, x_key: xKey, series, colors, axes, thresholds } = payload;
  // Hoisted so TypeScript can narrow it; a property access stays nullable.
  const ceiling = payload.max;

  if (payload.chart === "pie") {
    return (
      <PieChart>
        <Pie data={data} dataKey={series[0]} nameKey={xKey} innerRadius="45%">
          {data.map((row, i) => (
            <Cell key={String(row[xKey])} fill={pick(colors, i)} />
          ))}
        </Pie>
      </PieChart>
    );
  }

  // Radial never reaches here — the card renders <Gauge/> for it — but the map
  // has to be total for the type to narrow.
  const Cartesian = {
    line: LineChart,
    bar: BarChart,
    area: AreaChart,
    pie: LineChart,
    radial: LineChart,
  }[payload.chart];
  return (
    <Cartesian data={data} margin={{ left: 4, right: 12, top: 8 }}>
      {/* No grid behind the marks. This chart sits over a video on a TV, and
          rules drawn across it read as part of the picture, not as a scale.
          The axis labels carry the reading on their own. */}
      {/* An axis the caller turned off is hidden rather than left out: it still
          decides the scale — the order of the categories, the `max` ceiling —
          and recharts gives the space it would have taken back to the marks. */}
      <XAxis
        dataKey={xKey}
        tickLine={false}
        axisLine={false}
        tickMargin={8}
        hide={axes === "y" || axes === "none"}
      />
      <YAxis
        tickLine={false}
        axisLine={false}
        width={40}
        domain={ceiling == null ? undefined : [0, ceiling]}
        hide={axes === "x" || axes === "none"}
      />
      {series.map((key, i) => {
        const color = `var(--color-${key})`;
        if (payload.chart === "bar") {
          // Every bar answers for itself, so one hot core turns while the rest
          // stay the board's white — that is the whole point of a threshold on a
          // bar chart. Recharts reads cells by position, so it is all of them or
          // none: with no thresholds there are no cells and the bar is drawn
          // exactly as it was before this existed.
          return (
            <Bar key={key} dataKey={key} fill={color} radius={6}>
              {thresholds.length === 0
                ? null
                : data.map((row, r) => (
                    <Cell
                      key={`${String(row[xKey])}-${r}`}
                      fill={crossed(thresholds, Number(row[key])) ?? color}
                    />
                  ))}
            </Bar>
          );
        }
        // Line and area carry history, and Recharts would tween every point
        // between the old data and the new — the whole shape morphs instead of
        // the window sliding. Off, a new sample simply appears at the right and
        // the rest shifts, which is what a scrolling series should look like.
        if (payload.chart === "area") {
          return (
            <Area
              key={key}
              dataKey={key}
              stroke={color}
              fill={color}
              // The wash is what makes an area read as a fill under its line
              // rather than a solid block. A colour that carries its own alpha
              // has already been told how solid to be, so multiplying it again
              // would quietly make it a quarter of what was asked for.
              fillOpacity={carriesAlpha(pick(colors, i)) ? 1 : 0.25}
              isAnimationActive={false}
            />
          );
        }
        return (
          <Line
            key={key}
            dataKey={key}
            stroke={color}
            strokeWidth={3}
            dot={false}
            isAnimationActive={false}
          />
        );
      })}
    </Cartesian>
  );
}

/**
 * A chart drawn from data the caller supplied inline. The board never fetches.
 *
 * Recharts animates between datasets on its own, so writing the item again with
 * new numbers transitions rather than snapping.
 */
export function Chart({ id, payload }: { id: string; payload: ChartPayload }) {
  const { t } = useTranslation();
  // A gauge carries its identity in the middle of its ring; every other chart
  // carries it at the origin. Either way nothing is drawn above the plot, which
  // is why there is no header here any more: a header band costs its full
  // height whether the widget has height to spare or not, and on a chart that
  // wants to be a strip of bars it was most of the widget.
  const gauge = payload.chart === "radial";
  return (
    // Only a colour at an opacity. A border and a blur survive at zero opacity
    // and still draw a rectangle, which defeats the point of turning it down.
    <Card
      className={cn(
        "size-full border-0 widget-surface widget-edge shadow-none widget-text",
        gauge ? "py-0" : "py-3",
      )}
    >
      <CardContent
        className={cn("relative min-h-0 flex-1", gauge ? "p-0" : "px-3 pb-1")}
      >
        {payload.data.length === 0 ? (
          <div className="flex size-full items-center justify-center text-muted-foreground">
            {t("chart.noData")}
          </div>
        ) : gauge ? (
          <Gauge id={id} payload={payload} />
        ) : (
          <>
            <ChartContainer
              config={toConfig(payload.series, payload.colors)}
              className={`size-full ${AXIS_INK}`}
            >
              <Body payload={payload} />
            </ChartContainer>
            <Corner id={id} payload={payload} />
          </>
        )}
      </CardContent>
    </Card>
  );
}
