import { useTranslation } from "react-i18next";
import {
  Area,
  AreaChart,
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

/** Map each series onto a theme chart colour, the way shadcn expects. */
function toConfig(series: string[]): ChartConfig {
  return Object.fromEntries(
    series.map((key, i) => [
      key,
      { label: key, color: `var(--chart-${(i % SLOTS) + 1})` },
    ]),
  );
}

function Body({ payload }: { payload: ChartPayload }) {
  const { data, x_key: xKey, series } = payload;

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

  const Cartesian = { line: LineChart, bar: BarChart, area: AreaChart }[
    payload.chart
  ];
  return (
    <Cartesian data={data} margin={{ left: 4, right: 12, top: 8 }}>
      <CartesianGrid vertical={false} />
      <XAxis dataKey={xKey} tickLine={false} axisLine={false} tickMargin={8} />
      <YAxis tickLine={false} axisLine={false} width={40} />
      <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
      {series.length > 1 ? (
        <ChartLegend content={<ChartLegendContent />} />
      ) : null}
      {series.map((key) => {
        const color = `var(--color-${key})`;
        if (payload.chart === "bar") {
          return <Bar key={key} dataKey={key} fill={color} radius={6} />;
        }
        if (payload.chart === "area") {
          return (
            <Area
              key={key}
              dataKey={key}
              stroke={color}
              fill={color}
              fillOpacity={0.25}
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
    <Card className="size-full gap-2 py-3">
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
        ) : (
          <ChartContainer
            config={toConfig(payload.series)}
            className="size-full"
          >
            <Body payload={payload} />
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
