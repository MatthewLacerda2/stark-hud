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
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import type { ChartPayload } from "@/lib/schemas/board";
import { Chart } from "@/components/board/items/chart";
import "@/i18n";

const TRANSLUCENT = "#33ccffaa";
const ATTENTION = "#ffaa33";
const ALARM = "#ff3b30";
const SIZE = { width: 640, height: 360 };

beforeAll(() => {
  // The marks animate themselves in over real seconds. Nothing here is waiting
  // on a real clock — only on enough frames going by — so we hand the suite a
  // fake one and wind it forward instead of sitting through it.
  vi.useFakeTimers();
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

afterAll(() => {
  vi.useRealTimers();
});

async function render(payload: ChartPayload): Promise<HTMLElement> {
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
  thresholds: [],
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

/** What each bar was painted with, in the order they were drawn. */
function barFills(host: HTMLElement): (string | null)[] {
  return [...host.querySelectorAll(".recharts-rectangle")].map((bar) =>
    bar.getAttribute("fill"),
  );
}

/** What a gauge's filled arc was painted with — the track behind it aside. */
function arcFill(host: HTMLElement): string | null {
  return (
    host.querySelector(".recharts-radial-bar-sector")?.getAttribute("fill") ??
    null
  );
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

  it("says its title inside its ring, where the corner would be", async () => {
    // The gauge solved this first: a ring given the corner as well is a bigger
    // ring. Every other chart now says its title at the origin for the same
    // reason, so neither of them draws a header band any more.
    const host = await render(GAUGE);
    const titled = await render({ ...BARS, title: "Memory" });

    expect(host.textContent).toContain("Memory");
    expect(titled.textContent).toContain("Memory");
    expect(host.querySelector("[data-slot=card-header]")).toBe(null);
    expect(titled.querySelector("[data-slot=card-header]")).toBe(null);
  });

  it("gives a lone label the room the icon would have taken", async () => {
    const alone = await render(GAUGE);
    const paired = await render({
      ...GAUGE,
      icon: '<svg viewBox="0 0 24 24"><path d="M4 4h16"/></svg>',
    });

    const label = (host: HTMLElement) =>
      [...host.querySelectorAll("span")].find((s) =>
        s.className.includes("text-gauge-label"),
      )?.className ?? "";

    expect(label(alone)).toContain("text-gauge-label-alone");
    expect(label(paired)).not.toContain("text-gauge-label-alone");
  });

  it("draws an icon given as markup, beside the label", async () => {
    const host = await render({
      ...GAUGE,
      icon: '<svg viewBox="0 0 24 24"><path d="M4 4h16"/></svg>',
    });

    expect(host.querySelector('span > svg > path[d="M4 4h16"]')).not.toBe(null);
  });
});

describe("a chart's corner", () => {
  const MARK = '<svg viewBox="0 0 24 24"><path d="M4 4h16"/></svg>';

  it("is drawn by a bar chart, which used to throw it away", async () => {
    const host = await render({ ...BARS, icon: MARK });

    expect(host.querySelector('svg > path[d="M4 4h16"]')).not.toBe(null);
  });

  it("costs the plot no height, which is the whole point of the corner", async () => {
    // The corner is space the axes already frame. A mark that pushed the plot
    // down would be a header band with an icon in it, which is what this is not.
    const plain = await render(BARS);
    const marked = await render({ ...BARS, icon: MARK });

    expect(firstBarHeight(marked)).toBe(firstBarHeight(plain));
  });

  it("goes in a line, an area and a pie too, and leaves the gauge alone", async () => {
    for (const chart of ["line", "area", "pie"] as const) {
      const host = await render({ ...BARS, chart, icon: MARK });
      expect(host.querySelector('svg > path[d="M4 4h16"]')).not.toBe(null);
    }
    // A gauge draws its own in the middle of its ring, and only one of them.
    const gauge = await render({ ...GAUGE, icon: MARK });
    expect(gauge.querySelectorAll('svg > path[d="M4 4h16"]')).toHaveLength(1);
  });

  it("draws nothing at all when neither was given", async () => {
    const host = await render(BARS);

    expect(host.querySelector('[class*="text-chart-mark"]')).toBe(null);
  });

  it("costs the plot no height for a title either", async () => {
    // The header band this replaced pushed the plot down by its full height
    // whether the widget had height to spare or not. On a chart that wants to
    // be a strip of bars, that band was most of the widget.
    const plain = await render(BARS);
    const titled = await render({ ...BARS, title: "Commits this week" });

    expect(titled.textContent).toContain("Commits this week");
    expect(firstBarHeight(titled)).toBe(firstBarHeight(plain));
  });

  it("stacks the title under the icon, anchored to the top-left corner", async () => {
    const host = await render({ ...BARS, title: "CPU", icon: MARK });
    const corner = host.querySelector('[class*="text-chart-mark"]');

    expect(corner?.className).toContain("top-0");
    expect(corner?.className).toContain("left-0");
    // Icon first in the flow, so with the box pinned by its top edge the words
    // grow downward and the icon stays put against the corner.
    expect(corner?.firstElementChild?.querySelector("svg")).not.toBe(null);
    expect(corner?.lastElementChild?.textContent).toBe("CPU");
  });

  it("means something in all four combinations", async () => {
    const bare = await render(BARS);
    const marked = await render({ ...BARS, icon: MARK });
    const named = await render({ ...BARS, title: "CPU" });
    const both = await render({ ...BARS, title: "CPU", icon: MARK });

    expect(bare.querySelector('[class*="text-chart-mark"]')).toBe(null);
    expect(marked.textContent).not.toContain("CPU");
    expect(marked.querySelector('svg > path[d="M4 4h16"]')).not.toBe(null);
    expect(named.textContent).toContain("CPU");
    expect(named.querySelector('svg > path[d="M4 4h16"]')).toBe(null);
    expect(both.textContent).toContain("CPU");
    expect(both.querySelector('svg > path[d="M4 4h16"]')).not.toBe(null);
  });
});

describe("a threshold", () => {
  it("turns the bar that passed it and leaves its neighbour alone", async () => {
    // Monday is 3 and Tuesday is 7. Only Tuesday has anything to say.
    const host = await render({
      ...BARS,
      thresholds: [{ at: 5, color: ALARM }],
    });

    expect(barFills(host)).toEqual(["var(--color-hits)", ALARM]);
  });

  it("colours a gauge over the line, and not one under it", async () => {
    const hot = await render({
      ...GAUGE,
      thresholds: [{ at: 30, color: ALARM }],
    });
    const calm = await render({
      ...GAUGE,
      thresholds: [{ at: 60, color: ALARM }],
    });

    // The gauge reads 42, so 30 is passed and 60 is not.
    expect(arcFill(hot)).toBe(ALARM);
    expect(arcFill(calm)).toBe(TRANSLUCENT);
  });

  it("gives way to the highest one the value has cleared", async () => {
    // Listed alarm first, so anything that takes the first or the last match
    // instead of the highest would answer with the attention colour.
    const host = await render({
      ...GAUGE,
      thresholds: [
        { at: 40, color: ALARM },
        { at: 30, color: ATTENTION },
      ],
    });

    expect(arcFill(host)).toBe(ALARM);
  });

  it("means nothing to a pie or a line, which colour by series", async () => {
    const crossed = [{ at: 1, color: ALARM }];

    const pie = await render({ ...BARS, chart: "pie", thresholds: crossed });
    expect(pie.querySelector(".recharts-sector")?.getAttribute("fill")).toBe(
      TRANSLUCENT,
    );

    const line = await render({ ...BARS, chart: "line", thresholds: crossed });
    expect(
      line.querySelector(".recharts-line-curve")?.getAttribute("stroke"),
    ).toBe("var(--color-hits)");
  });

  it("leaves a chart exactly as it was when there is none to cross", async () => {
    const plain = await render(BARS);
    const unreached = await render({
      ...BARS,
      thresholds: [{ at: 100, color: ALARM }],
    });

    // An empty list is what every chart on this board carries, so it has to
    // paint the marks with the colour they were asked for and nothing else.
    expect(barFills(plain)).toEqual(["var(--color-hits)", "var(--color-hits)"]);
    expect(barFills(unreached)).toEqual(barFills(plain));
  });
});
