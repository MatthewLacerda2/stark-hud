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
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartPayload } from "@/lib/schemas/board";

// Series colours come from the theme, so charts follow the palette like
// everything else. Recharts needs real values, so these are the CSS vars.
const COLORS = [1, 2, 3, 4, 5, 6].map((n) => `var(--color-chart-${n})`);

const AXIS = { stroke: "var(--color-muted-foreground)", fontSize: 14 };

function Body({ payload }: { payload: ChartPayload }) {
  const { data, x_key: xKey, series } = payload;

  if (payload.chart === "pie") {
    return (
      <PieChart>
        <Pie data={data} dataKey={series[0]} nameKey={xKey} outerRadius="80%">
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
      </PieChart>
    );
  }

  const Cartesian = { line: LineChart, bar: BarChart, area: AreaChart }[
    payload.chart
  ];
  return (
    <Cartesian data={data}>
      <CartesianGrid stroke="var(--color-border)" vertical={false} />
      <XAxis dataKey={xKey} {...AXIS} />
      <YAxis {...AXIS} />
      <Tooltip />
      {series.map((key, i) => {
        const color = COLORS[i % COLORS.length];
        if (payload.chart === "bar")
          return <Bar key={key} dataKey={key} fill={color} />;
        if (payload.chart === "area")
          return (
            <Area
              key={key}
              dataKey={key}
              stroke={color}
              fill={color}
              fillOpacity={0.3}
            />
          );
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

/** A chart drawn from data the caller supplied inline. The board never fetches. */
export function Chart({ payload }: { payload: ChartPayload }) {
  const { t } = useTranslation();
  return (
    <div className="flex size-full flex-col rounded-xl bg-card p-3">
      {payload.title ? (
        <h3 className="mb-1 text-h3 text-muted-foreground">{payload.title}</h3>
      ) : null}
      <div className="min-h-0 flex-1">
        {payload.data.length === 0 ? (
          <div className="flex size-full items-center justify-center text-body text-muted-foreground">
            {t("chart.noData")}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <Body payload={payload} />
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
