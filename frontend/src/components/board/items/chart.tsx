import { useTranslation } from "react-i18next";
import {
  Area,
  AreaChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartPayload } from "@/lib/schemas/board";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SLOTS = 5;

/** The colour for series `i`: whatever was asked for, else the next default. */
function pick(colors: string[], i: number): string {
  return colors.length > 0
    ? colors[i % colors.length]
    : `var(--chart-${(i % SLOTS) + 1})`;
}

/** Map each series onto a colour, the way shadcn's ChartConfig expects. */
function toConfig(series: string[], colors: string[]): ChartConfig {
  return Object.fromEntries(
    series.map((key, i) => [key, { label: key, color: pick(colors, i) }]),
  );
}

/** A gauge: one number, drawn as an arc of its ceiling. */
function Gauge({ payload }: { payload: ChartPayload }) {
  const row = payload.data[0];
  const ceiling = payload.max ?? 100;
  const value = Number(row[payload.series[0]] ?? 0);
  const fraction = Math.min(Math.max(value / ceiling, 0), 1);

  return (
    <div className="relative size-full">
      <ChartContainer
        config={toConfig(payload.series, payload.colors)}
        className="size-full"
      >
        <RadialBarChart
          data={[{ ...row, __fill: pick(payload.colors, 0) }]}
          startAngle={90}
          endAngle={90 - 360 * fraction}
          innerRadius="72%"
          outerRadius="100%"
        >
          <PolarAngleAxis
            type="number"
            domain={[0, ceiling]}
            tick={false}
            axisLine={false}
          />
          <RadialBar
            dataKey={payload.series[0]}
            background
            cornerRadius={999}
            fill={pick(payload.colors, 0)}
          />
        </RadialBarChart>
      </ChartContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-gauge text-foreground">
          {Math.round(value)}
          {payload.unit ? (
            <span className="text-gauge-label text-muted-foreground">
              {payload.unit}
            </span>
          ) : null}
        </span>
        <span className="text-gauge-label text-muted-foreground">
          {String(row[payload.x_key] ?? "")}
        </span>
      </div>
    </div>
  );
}

function Body({ payload }: { payload: ChartPayload }) {
  const { data, x_key: xKey, series } = payload;
  // Hoisted so TypeScript can narrow it; a property access stays nullable.
  const ceiling = payload.max;

  if (payload.chart === "pie") {
    return (
      <PieChart>
        <ChartTooltip
          content={<ChartTooltipContent nameKey={xKey} hideLabel />}
        />
        <Pie data={data} dataKey={series[0]} nameKey={xKey} innerRadius="45%">
          {data.map((row, i) => (
            <Cell
              key={String(row[xKey])}
              fill={`var(--chart-${(i % SLOTS) + 1})`}
            />
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
      <CartesianGrid vertical={false} />
      <XAxis dataKey={xKey} tickLine={false} axisLine={false} tickMargin={8} />
      <YAxis
        tickLine={false}
        axisLine={false}
        width={40}
        domain={ceiling == null ? undefined : [0, ceiling]}
      />
      <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
      {series.length > 1 ? (
        <ChartLegend content={<ChartLegendContent />} />
      ) : null}
      {series.map((key) => {
        const color = `var(--color-${key})`;
        if (payload.chart === "bar") {
          return <Bar key={key} dataKey={key} fill={color} radius={6} />;
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
              fillOpacity={0.25}
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
export function Chart({ payload }: { payload: ChartPayload }) {
  const { t } = useTranslation();
  return (
    // Only a colour at an opacity. A border and a blur survive at zero opacity
    // and still draw a rectangle, which defeats the point of turning it down.
    <Card className="size-full gap-2 border-0 tile-surface py-3 shadow-none">
      {payload.title ? (
        <CardHeader className="px-4">
          <CardTitle>{payload.title}</CardTitle>
        </CardHeader>
      ) : null}
      <CardContent className="min-h-0 flex-1 px-3 pb-1">
        {payload.data.length === 0 ? (
          <div className="flex size-full items-center justify-center text-muted-foreground">
            {t("chart.noData")}
          </div>
        ) : payload.chart === "radial" ? (
          <Gauge payload={payload} />
        ) : (
          <ChartContainer
            config={toConfig(payload.series, payload.colors)}
            className="size-full"
          >
            <Body payload={payload} />
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
