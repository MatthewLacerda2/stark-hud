/**
 * What a chart actually drew, read back off the SVG.
 *
 * A payload passes through shadcn's chart container and recharts before it is
 * anything anyone can look at: colours become CSS variables somewhere in the
 * middle, and an axis decides how much of the widget the marks get. Both are
 * several steps from what the caller asked for, so this renders real charts and
 * reads what came out rather than asserting on the props on the way in.
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
    createRoot(host).render(<Chart id="widget-1" payload={payload} />);
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
  icon: null,
  max: null,
  unit: null,
  axes: "both",
  unfilled: null,
  colors: [TRANSLUCENT],
};

const GAUGE: ChartPayload = {
  ...BARS,
  chart: "radial",
  data: [{ day: "GPU", hits: 42 }],
  title: "Memory",
  max: 100,
  unit: "%",
};

/** The widest arc a path draws: for a ring, the radius of its outer edge. */
function outerRadius(path: Element | null): number {
  // A sector that closes the whole circle is written `A 179.6,...`, with the
  // space a partial one does not have.
  const arcs = [...(path?.getAttribute("d") ?? "").matchAll(/A\s*([\d.]+),/g)];
  return Math.max(...arcs.map((arc) => Number(arc[1])));
}

/** The shape of one of a radial chart's sectors, as it was actually drawn. */
function sectorPath(host: HTMLElement, selector: string): string {
  return host.querySelector(selector)?.getAttribute("d") ?? "";
}

/** How far in from the left edge the marks start. */
function firstBarX(host: HTMLElement): number {
  return Number(host.querySelector(".recharts-rectangle")?.getAttribute("x"));
}

/** How tall the first bar came out, in pixels of the plot it sits in. */
function firstBarHeight(host: HTMLElement): number {
  return Number(
    host.querySelector(".recharts-rectangle")?.getAttribute("height"),
  );
}

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

describe("an axis the caller left out", () => {
  it("is gone, while the one they kept is not", async () => {
    const host = await render({ ...BARS, axes: "y" });

    expect(host.querySelector(".recharts-xAxis")).toBe(null);
    expect(host.querySelector(".recharts-yAxis")).not.toBe(null);
  });

  it("gives the room it was taking to the marks", async () => {
    const host = await render({ ...BARS, axes: "none" });

    expect(host.querySelector(".recharts-cartesian-axis")).toBe(null);
    expect(host.querySelector(".recharts-rectangle")).not.toBe(null);
    // The room the labels were taking is the point of leaving them out.
    expect(firstBarX(host)).toBeLessThan(firstBarX(await render(BARS)));
  });

  it("still decides the scale it is no longer drawing", async () => {
    // A ceiling is set on the y axis, so an axis that is merely hidden has to
    // stay: dropped, a bar of 7 would fill the plot whatever `max` said.
    const capped = await render({ ...BARS, axes: "none", max: 20 });
    const fitted = await render({ ...BARS, axes: "none" });

    expect(firstBarHeight(capped)).toBeLessThan(firstBarHeight(fitted));
  });
});

describe("a gauge", () => {
  it("draws its ring out to the edge of the space it was given", async () => {
    const host = await render(GAUGE);

    // Within a pixel of half the shorter side: the ring touches two edges of
    // the widget, rather than sitting inside a margin and a bar gap.
    const track = host.querySelector(".recharts-radial-bar-background-sector");
    expect(outerRadius(track)).toBeGreaterThan(SIZE.height / 2 - 1);
  });

  it("closes the track around the whole circle, behind the value", async () => {
    const TRACK = ".recharts-radial-bar-background-sector";
    const BAR = ".recharts-radial-bar-sector";
    const low = await render(GAUGE);
    const high = await render({ ...GAUGE, data: [{ day: "GPU", hits: 90 }] });

    // The value moves the bar and nothing else. When the chart's own angular
    // extent was the value, the track could only be the arc the bar already
    // covered — so it moved too, and the rest of the ring did not exist.
    expect(sectorPath(low, BAR)).not.toBe(sectorPath(high, BAR));
    expect(sectorPath(low, TRACK)).toBe(sectorPath(high, TRACK));
    // And what it draws is the closed ring: one arc all the way round.
    expect(sectorPath(low, TRACK)).toContain("1,1,");
  });

  it("says who it is, and stops saying what the ring already says", async () => {
    const host = await render(GAUGE);

    expect(host.textContent).toContain("Memory");
    // The row's own label, spelled the way whatever collected it spelled it.
    expect(host.textContent).toContain("GPU");
    // The ring is the proportion; a big 42 beside it was saying it twice.
    expect(host.textContent).not.toContain("42");
    expect(host.textContent).not.toContain("%");
  });

  it("keeps its title out of the corner the chart card draws one in", async () => {
    const host = await render(GAUGE);
    const titled = await render({ ...BARS, title: "Memory" });

    expect(host.querySelector("[data-slot=card-title]")).toBe(null);
    expect(titled.querySelector("[data-slot=card-title]")?.textContent).toBe(
      "Memory",
    );
  });

  it("draws an icon given as markup, beside the label", async () => {
    const host = await render({
      ...GAUGE,
      icon: '<svg viewBox="0 0 24 24"><path d="M4 4h16"/></svg>',
    });

    expect(host.querySelector('span > svg > path[d="M4 4h16"]')).not.toBe(null);
  });
});
