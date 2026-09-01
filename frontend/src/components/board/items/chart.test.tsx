/**
 * A colour with alpha in it has to reach the marks, not just the payload.
 *
 * The colours a caller sends go into shadcn's chart container, which writes them
 * into a stylesheet, and the marks then name a CSS variable rather than a colour.
 * That is several places for an eight-digit hex to be re-parsed and quietly lose
 * its alpha, so this renders real charts and reads what actually came out.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeAll, describe, expect, it } from "vitest";
import type { ChartPayload } from "@/lib/schemas/board";
import { Chart } from "@/components/board/items/chart";
import "@/i18n";

const TRANSLUCENT = "#33ccffaa";
const SIZE = { width: 640, height: 360 };

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  // jsdom lays nothing out and never paints a frame. A chart that sizes itself
  // to its container would draw at nothing, and one that animates its marks in
  // would never finish doing so — leaving no marks at all to look at.
  globalThis.ResizeObserver = class {
    fire: ResizeObserverCallback;
    constructor(fire: ResizeObserverCallback) {
      this.fire = fire;
    }
    observe(target: Element) {
      this.fire(
        [{ target, contentRect: SIZE } as unknown as ResizeObserverEntry],
        this as unknown as ResizeObserver,
      );
    }
    unobserve() {}
    disconnect() {}
  };
  let clock = 0;
  globalThis.requestAnimationFrame = (run: FrameRequestCallback) => {
    clock += 500;
    return setTimeout(() => run(clock), 0) as unknown as number;
  };
  globalThis.cancelAnimationFrame = (id: number) => clearTimeout(id);
  Object.defineProperty(HTMLElement.prototype, "getBoundingClientRect", {
    configurable: true,
    value: () => ({
      ...SIZE,
      top: 0,
      left: 0,
      right: SIZE.width,
      bottom: SIZE.height,
      x: 0,
      y: 0,
    }),
  });
});

async function render(payload: ChartPayload): Promise<HTMLElement> {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(<Chart payload={payload} />);
  });
  // Long enough for every mark's entrance animation to land on its final value.
  await act(async () => {
    await new Promise((done) => setTimeout(done, 1600));
  });
  return host;
}

const BARS: ChartPayload = {
  kind: "chart",
  chart: "bar",
  data: [
    { day: "Mon", hits: 3 },
    { day: "Tue", hits: 7 },
  ],
  x_key: "day",
  series: ["hits"],
  title: null,
  max: null,
  unit: null,
  colors: [TRANSLUCENT],
};

describe("a chart colour that carries alpha", () => {
  it("reaches a bar, through the variable it is painted with", async () => {
    const host = await render(BARS);

    const style = host.querySelector("style")?.textContent ?? "";
    expect(style).toContain(`--color-hits: ${TRANSLUCENT}`);
    expect(
      host.querySelector(".recharts-rectangle")?.getAttribute("fill"),
    ).toBe("var(--color-hits)");
  });

  it("reaches a line's stroke and a pie's slices", async () => {
    const line = await render({ ...BARS, chart: "line" });
    expect(
      line.querySelector(".recharts-line-curve")?.getAttribute("stroke"),
    ).toBe("var(--color-hits)");

    const pie = await render({ ...BARS, chart: "pie" });
    expect(pie.querySelector(".recharts-sector")?.getAttribute("fill")).toBe(
      TRANSLUCENT,
    );
  });

  it("does not get an area's wash applied on top of it", async () => {
    const opaque = await render({
      ...BARS,
      chart: "area",
      colors: ["#33ccff"],
    });
    expect(
      opaque.querySelector(".recharts-area-area")?.getAttribute("fill-opacity"),
    ).toBe("0.25");

    const asked = await render({ ...BARS, chart: "area" });
    expect(
      asked.querySelector(".recharts-area-area")?.getAttribute("fill-opacity"),
    ).toBe("1");
  });

  it("is what the axis labels are painted with", async () => {
    const host = await render(BARS);
    const classes = host.querySelector("[data-slot=chart]")?.className ?? "";

    expect(classes).toContain(
      "[&_.recharts-cartesian-axis-tick-value]:fill-[var(--widget-text,var(--color-muted-foreground))]",
    );
    // The rule is only worth anything if it still names what recharts renders.
    expect(classes).not.toContain("fill-muted-foreground");
    expect(host.querySelector(".recharts-cartesian-axis-tick-value")).not.toBe(
      null,
    );
  });
});
