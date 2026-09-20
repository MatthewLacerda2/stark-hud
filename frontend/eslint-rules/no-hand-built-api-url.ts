import { type TSESTree } from "@typescript-eslint/utils";
import { createRule } from "./utils";

// The prefix `client.ts` owns. Written out rather than read from anywhere: a
// lint rule that imports the value it is guarding would pass the day somebody
// changes the value and every hand-built URL along with it.
const BASE = "/api/v1";

export const noHandBuiltApiUrl = createRule({
  name: "no-hand-built-api-url",
  meta: {
    type: "problem",
    docs: {
      description:
        "Forbid spelling the API base outside lib/api; one module knows where the backend is.",
    },
    messages: {
      built:
        "'{{text}}' builds its own API URL. `lib/api/client.ts` is the one place that knows where the backend is — call a `lib/api/` function (`mediaUrl`, `iconUrl`, `trackUrl`) instead. A URL written here is one `VITE_API_URL` cannot move, which is how the pictures stayed behind when the JSON moved.",
    },
    schema: [],
  },
  defaultOptions: [],
  create(context) {
    /** Report a string that names the API base, whatever quoted it. */
    function check(node: TSESTree.Node, value: string) {
      if (!value.includes(BASE)) return;
      context.report({
        node,
        messageId: "built",
        data: { text: value.length > 40 ? `${value.slice(0, 40)}…` : value },
      });
    }

    return {
      // A plain string: `src="/api/v1/media/background"`.
      Literal(node: TSESTree.Literal) {
        if (typeof node.value === "string") check(node, node.value);
      },
      // A template, which is how all but one of these were written, because
      // every one of them had an id to interpolate. Only the fixed parts are
      // read: `${id}` cannot contain the base.
      TemplateElement(node: TSESTree.TemplateElement) {
        check(node, node.value.cooked ?? node.value.raw);
      },
    };
  },
});
