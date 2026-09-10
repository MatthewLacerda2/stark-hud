/**
 * A real chart, rendered in jsdom, for a test to read the SVG back off.
 *
 * Shared by the chart suites rather than copied into each. jsdom lays nothing
 * out and never paints a frame, so a chart that sizes itself to its container
 * draws at nothing and one that animates its marks in never finishes doing so —
 * leaving no marks at all to look at. All of that has to be faked before any of
 * these tests mean anything, and faking it twice is how two suites come to
 * disagree about what a chart was drawn into.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterAll, beforeAll, vi } from "vitest";
import type { ChartPayload } from "@/lib/schemas/board";
import { Chart } from "@/components/board/items/chart";
import "@/i18n";

/** How big the harness pretends the widget is. A test that measures needs it. */
export const SIZE = { width: 640, height: 360 };

/** Give the suite a screen to draw on and a clock to wind. Call it at top level. */
export function stubLayout(): void {
  beforeAll(() => {
    // The marks animate themselves in over real seconds. Nothing here is
    // waiting on a real clock — only on enough frames going by — so we hand the
    // suite a fake one and wind it forward instead of sitting through it.
    vi.useFakeTimers();
    (
      globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
    ).IS_REACT_ACT_ENVIRONMENT = true;
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

  afterAll(() => {
    vi.useRealTimers();
  });
}

/** One chart on the page, with every entrance animation already landed. */
export async function render(payload: ChartPayload): Promise<HTMLElement> {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(<Chart id="widget-1" payload={payload} />);
  });
  // Long enough for every mark's entrance animation to land on its final value.
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1600);
  });
  return host;
}

/** The plainest chart there is: two bars, one series, both axes drawn. */
export const BARS: ChartPayload = {
  kind: "chart",
  chart: "bar",
  data: [
    { day: "Mon", hits: 3 },
    { day: "Tue", hits: 7 },
  ],
  x_key: "day",
  series: ["hits"],
  title: null,
  icon: null,
  max: null,
  unit: null,
  axes: "both",
  unfilled: null,
  colors: ["#33ccffaa"],
  thresholds: [],
};
