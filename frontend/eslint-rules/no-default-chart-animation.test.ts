import { createTester } from "./tester";
import { noDefaultChartAnimation } from "./no-default-chart-animation";

const tester = createTester();

tester.run("no-default-chart-animation", noDefaultChartAnimation, {
  valid: [
    {
      code: `import { Line } from "recharts"; const x = <Line dataKey="a" isAnimationActive={false} />;`,
    },
    {
      code: `import { Radar } from "recharts"; const x = <Radar dataKey="a" animationDuration={SWEEP_MS} />;`,
    },
    // Not a series: axes and cells do not animate.
    {
      code: `import { XAxis, Cell } from "recharts"; const x = <XAxis /> && <Cell />;`,
    },
    // A component of the same name that is not recharts'.
    {
      code: `import { Line } from "./shapes"; const x = <Line />;`,
    },
  ],
  invalid: [
    // The two #176 found: a pie and a bar left at the default.
    {
      code: `import { Pie } from "recharts"; const x = <Pie data={d} dataKey="a" />;`,
      errors: [{ messageId: "undecided", data: { name: "Pie" } }],
    },
    {
      code: `import { Bar } from "recharts"; const x = <Bar dataKey="a"><Cell /></Bar>;`,
      errors: [{ messageId: "undecided", data: { name: "Bar" } }],
    },
    // Renaming the import does not hide it.
    {
      code: `import { Bar as Column } from "recharts"; const x = <Column dataKey="a" />;`,
      errors: [{ messageId: "undecided", data: { name: "Bar" } }],
    },
  ],
});
