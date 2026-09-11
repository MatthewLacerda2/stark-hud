import { type TSESTree } from "@typescript-eslint/utils";
import { classTokens, createRule } from "./utils";

// The padding utilities, including the logical ones nobody has reached for yet.
const PADDING = /^(p|px|py|pt|pb|pl|pr|ps|pe)-(.+)$/;

// A length measured against the widget's own container query box. `cqmin` is
// the one the board already uses; the rest are here so the rule does not have
// to be edited the first time somebody wants a different axis.
const CONTAINER_UNIT = /\d(cqmin|cqmax|cqw|cqh|cqi|cqb)\b/;

/** Strip a responsive, state or container prefix (`md:`, `hover:`, `@lg:`). */
function bareToken(token: string): string {
  const at = token.lastIndexOf(":");
  return at === -1 ? token : token.slice(at + 1);
}

/** Whether this padding value holds a widget's drawing back by a fixed amount. */
function isFixed(value: string): boolean {
  // Zero is what the radial does, and the radial is the reference.
  if (value === "0") return false;
  if (value.startsWith("[") && value.endsWith("]"))
    return !CONTAINER_UNIT.test(value);
  return true;
}

export const noFixedWidgetInset = createRule({
  name: "no-fixed-widget-inset",
  meta: {
    type: "problem",
    docs: {
      description:
        "Forbid fixed-pixel padding on board widgets; inset is a share of the widget.",
    },
    messages: {
      fixed:
        "'{{token}}' insets this widget by a fixed amount. A widget is judged from a sofa and its drawing should reach its boundary the way a radial's ring does, so inset is a share of the widget: use a container unit ('p-[4cqmin]') or none at all.",
    },
    schema: [],
  },
  defaultOptions: [],
  create(context) {
    // Only the widgets. Everything else on the page is read from a normal
    // distance and a pixel means there what a pixel usually means.
    if (!/[\\/]components[\\/]board[\\/]items[\\/]/.test(context.filename))
      return {};

    /**
     * Every string literal, not only a `className` attribute.
     *
     * The widgets that most need this are the ones that pick a class — the
     * chart's `gauge ? "py-0" : "py-3"` is the very line the issue was written
     * about, and it reaches JSX inside a `cn()` call where an attribute-only
     * rule sees an expression and gives up. Nothing else in these files is a
     * string that looks like a padding utility.
     */
    return {
      Literal(node: TSESTree.Literal) {
        if (typeof node.value !== "string") return;
        for (const token of classTokens(node.value)) {
          const found = PADDING.exec(bareToken(token));
          if (found && isFixed(found[2])) {
            context.report({ node, messageId: "fixed", data: { token } });
          }
        }
      },
    };
  },
});
