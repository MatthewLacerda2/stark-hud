import { type TSESTree } from "@typescript-eslint/utils";
import { createRule } from "./utils";

// Every recharts component that draws a series and animates it on its own
// unless told otherwise. Axes, grids and cells do not animate; these do, and
// their default is 1500 ms of motion after every sample.
const SERIES = new Set([
  "Area",
  "Bar",
  "Funnel",
  "Line",
  "Pie",
  "Radar",
  "RadialBar",
  "Scatter",
]);

// Either one says what was wanted: off, or a duration somebody chose.
const DECIDED = new Set(["isAnimationActive", "animationDuration"]);

export const noDefaultChartAnimation = createRule({
  name: "no-default-chart-animation",
  meta: {
    type: "problem",
    docs: {
      description:
        "A recharts series must say how it animates; the library's default is nobody's decision.",
    },
    messages: {
      undecided:
        "<{{name}}> animates at recharts' default of 1500 ms after every sample, which nobody here chose. Say what it should do: isAnimationActive={false} for a series whose window slides, or animationDuration={SWEEP_MS} for one whose marks stay put. See SWEEP_MS in chart-marks.ts.",
    },
    schema: [],
  },
  defaultOptions: [],
  create(context) {
    // Local names bound to a recharts series, so a renamed import is still
    // caught and an unrelated component called `Line` is not.
    const series = new Map<string, string>();

    return {
      ImportDeclaration(node: TSESTree.ImportDeclaration) {
        if (node.source.value !== "recharts") return;
        for (const spec of node.specifiers) {
          if (spec.type !== "ImportSpecifier") continue;
          const imported =
            spec.imported.type === "Identifier"
              ? spec.imported.name
              : spec.imported.value;
          if (SERIES.has(imported)) series.set(spec.local.name, imported);
        }
      },
      JSXOpeningElement(node: TSESTree.JSXOpeningElement) {
        if (node.name.type !== "JSXIdentifier") return;
        const name = series.get(node.name.name);
        if (name === undefined) return;
        const decided = node.attributes.some(
          (a) =>
            a.type === "JSXAttribute" &&
            a.name.type === "JSXIdentifier" &&
            DECIDED.has(a.name.name),
        );
        if (!decided)
          context.report({ node, messageId: "undecided", data: { name } });
      },
    };
  },
});
