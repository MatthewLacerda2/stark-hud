import { createTester } from "./tester";
import { noFixedWidgetInset } from "./no-fixed-widget-inset";

const tester = createTester();

/** A path the rule watches, and one it deliberately does not. */
const WIDGET = "/repo/frontend/src/components/board/items/note.tsx";
const ELSEWHERE = "/repo/frontend/src/components/ui/card.tsx";

tester.run("no-fixed-widget-inset", noFixedWidgetInset, {
  valid: [
    {
      filename: WIDGET,
      code: `const x = <div className="p-[4cqmin]">hi</div>;`,
    },
    {
      filename: WIDGET,
      code: `const x = <div className="px-[2cqmin] pb-[0.75cqmin]">hi</div>;`,
    },
    // The radial's own inset, and the one this rule is arguing towards.
    { filename: WIDGET, code: `const x = <div className="p-0">hi</div>;` },
    // Not a padding utility at all.
    {
      filename: WIDGET,
      code: `const x = <div className="gap-2 flex size-full">hi</div>;`,
    },
    // The rest of the page is read from a normal distance.
    { filename: ELSEWHERE, code: `const x = <div className="p-4">hi</div>;` },
  ],
  invalid: [
    {
      filename: WIDGET,
      code: `const x = <div className="p-5">hi</div>;`,
      errors: [{ messageId: "fixed" }],
    },
    // The line the issue was written about: a class picked inside cn(), where a
    // className-attribute rule sees an expression and gives up.
    {
      filename: WIDGET,
      code: `const x = <div className={cn("relative", gauge ? "p-0" : "px-3 pb-1")}>hi</div>;`,
      errors: [{ messageId: "fixed" }, { messageId: "fixed" }],
    },
    // An arbitrary value is not automatically a share of the widget.
    {
      filename: WIDGET,
      code: `const x = <div className="p-[20px]">hi</div>;`,
      errors: [{ messageId: "fixed" }],
    },
    {
      filename: WIDGET,
      code: `const x = <div className="@lg:py-3">hi</div>;`,
      errors: [{ messageId: "fixed" }],
    },
  ],
});
