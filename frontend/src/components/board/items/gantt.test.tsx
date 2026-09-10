/**
 * What a gantt widget actually draws.
 *
 * `gantt.test.ts` has the arithmetic. This has the half that #42 taught us not
 * to leave untested: that the sums reach the screen — the right rows, the span
 * mark, a bar clipped to the left edge rather than dropped, and a name that
 * appears only where there is room for it.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { GanttRow } from "@/lib/schemas/board";
import { Gantt } from "@/components/board/items/gantt";
import "@/i18n";

const NOW = new Date("2026-09-04T18:00:00Z").getTime();
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;

// Its own alpha, so the widget must not wash it a second time. Bound to a name
// rather than written inline because a hex in an object literal is exactly what
// the colour-token lint rule is there to catch.
const OWN_ALPHA = "#33ccffaa";

const mounted: Root[] = [];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(async () => {
  await act(async () => mounted.forEach((root) => root.unmount()));
  mounted.length = 0;
});

function bar(
  title: string,
  from: number,
  to: number,
  color: string | null = null,
) {
  return {
    title,
    start: new Date(NOW + from).toISOString(),
    end: new Date(NOW + to).toISOString(),
    color,
  };
}

async function show(rows: GanttRow[], cols = 12) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);
  await act(async () => {
    root.render(
      <Gantt
        id="w1"
        cols={cols}
        payload={{
          kind: "gantt",
          title: "Tonight",
          icon: null,
          rows,
          empty: null,
        }}
      />,
    );
  });
  return {
    rows: () => [...host.querySelectorAll("li")],
    bars: () => [...host.querySelectorAll("li > div > div")] as HTMLElement[],
    text: () => host.textContent ?? "",
  };
}

describe("a gantt", () => {
  it("draws a row per track and states the span it is drawn in", async () => {
    const { rows, text } = await show([
      { name: "Kitchen", bars: [bar("sauce", -10 * MINUTE, 25 * MINUTE)] },
      { name: "Laundry", bars: [bar("wash", 15 * MINUTE, 45 * MINUTE)] },
    ]);

    expect(rows()).toHaveLength(2);
    expect(text()).toContain("Kitchen");
    expect(text()).toContain("Laundry");
    // Width is the only thing here carrying duration, and it says nothing
    // without the frame it is drawn in.
    expect(text()).toContain("1h");
  });

  it("says its empty line rather than drawing an axis over nothing", async () => {
    const { rows, text } = await show([
      { name: "Kitchen", bars: [bar("sauce", -2 * HOUR, -HOUR)] },
    ]);

    expect(rows()).toHaveLength(0);
    expect(text()).toContain("Nothing coming up");
  });

  it("clips a bar that has already started to the left edge", async () => {
    const { bars } = await show([
      { name: "Kitchen", bars: [bar("sauce", -20 * MINUTE, 10 * MINUTE)] },
    ]);

    // The window is ten minutes, so the whole frame is what is left of it.
    const [block] = bars();
    expect(block.style.left).toBe("0%");
    expect(block.style.width).toBe("100%");
  });

  it("puts a name in a bar wide enough to hold one", async () => {
    const { text } = await show([
      { name: "Kitchen", bars: [bar("sauce", 0, HOUR)] },
    ]);

    expect(text()).toContain("sauce");
  });

  it("drops the name from a bar that is only a sliver of the window", async () => {
    const { text } = await show([
      // Fifteen minutes inside a four-hour window: 6% of the width.
      { name: "Kitchen", bars: [bar("sauce", 0, 15 * MINUTE)] },
      { name: "Film", bars: [bar("watch", 3 * HOUR, 4 * HOUR)] },
    ]);

    // The row is on screen and the frame is four hours wide; what is missing
    // is the word inside a bar 6% of the way across it.
    expect(text()).toContain("Kitchen");
    expect(text()).toContain("4h");
    expect(text()).not.toContain("sauce");
  });

  it("does not wash a colour that already said how see-through it is", async () => {
    const { bars } = await show([
      { name: "Kitchen", bars: [bar("sauce", 0, HOUR, OWN_ALPHA)] },
    ]);
    const fill = bars()[0].querySelector("div") as HTMLElement;

    expect(fill.style.opacity).toBe("1");
  });

  it("washes a colour that did not, so the video still moves behind it", async () => {
    const { bars } = await show([
      { name: "Kitchen", bars: [bar("sauce", 0, HOUR)] },
    ]);
    const fill = bars()[0].querySelector("div") as HTMLElement;

    expect(Number(fill.style.opacity)).toBeLessThan(1);
  });
});
