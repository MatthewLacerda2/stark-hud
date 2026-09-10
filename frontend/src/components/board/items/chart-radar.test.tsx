/**
 * What a radar drew, read back off the SVG.
 *
 * Its own file rather than one more suite beside the cartesian charts: a radar
 * is read as a shape rather than as a set of values, so what these assert on is
 * the polygon and the reticle behind it, not heights and axis labels.
 */
import { describe, expect, it } from "vitest";
import type { ChartPayload } from "@/lib/schemas/board";
import {
  BARS,
  render,
  stubLayout,
} from "@/components/board/items/chart-render";

stubLayout();

describe("a radar", () => {
  const RADAR: ChartPayload = {
    ...BARS,
    chart: "radar",
    data: [
      { day: "0", hits: 90 },
      { day: "1", hits: 5 },
      { day: "2", hits: 5 },
      { day: "3", hits: 5 },
    ],
    max: 100,
  };

  /**
   * The polygon the values actually drew, as its list of points.
   *
   * Recharts closes the shape by repeating the first point, so the last one is
   * dropped and what comes back is one corner per row.
   */
  function corners(host: HTMLElement): [number, number][] {
    const shape = host.querySelector(".recharts-radar-polygon path");
    const points = (shape?.getAttribute("d") ?? "")
      .split(/[ML]/)
      .filter(Boolean)
      .map((pair) => pair.split(",").map(Number) as [number, number]);
    return points.slice(0, -1);
  }

  it("draws one corner per row, painted with the colour asked for", async () => {
    const host = await render(RADAR);

    expect(corners(host)).toHaveLength(4);
    expect(
      host
        .querySelector(".recharts-radar-polygon path")
        ?.getAttribute("stroke"),
    ).toBe("var(--color-hits)");
  });

  it("keeps its grid, so an idle machine is quiet rather than broken", async () => {
    const idle = await render({
      ...RADAR,
      data: RADAR.data.map((row) => ({ ...row, hits: 2 })),
    });

    // The polygon has collapsed to nearly nothing; the reticle it sits in has
    // not, and that is what stops the widget reading as empty.
    expect(idle.querySelectorAll(".recharts-polar-grid line").length).toBe(4);
    expect(
      idle.querySelectorAll(".recharts-polar-grid-angle line").length,
    ).toBeGreaterThan(0);
  });

  it("says nothing on its spokes, and grows no spurs pointing at where it would", async () => {
    const host = await render(RADAR);

    // The angle axis is declared for the spokes it positions, not for anything
    // it draws — labels, tick marks and a second outer ring all come off. It
    // still emits an empty group per tick, which is why this counts what paints
    // rather than what recharts happens to wrap it in.
    const axis = host.querySelector(".recharts-polar-angle-axis");
    expect(axis?.querySelectorAll("text").length).toBe(0);
    expect(
      axis?.querySelectorAll(".recharts-polar-angle-axis-tick-line").length,
    ).toBe(0);
    expect(
      axis?.querySelectorAll(".recharts-polar-angle-axis-line").length,
    ).toBe(0);
  });

  /**
   * The ceiling is the point. Without it recharts fits the radius to whatever
   * arrived, so four cores idling at 2% would draw the same polygon as four
   * cores pegged — the shape would say "one of them is the busiest" instead of
   * "this machine is busy", which is not the question anybody asks from a sofa.
   */
  it("draws against the ceiling and not against the largest value", async () => {
    const centre = (host: HTMLElement) => corners(host)[1];

    const hot = await render(RADAR);
    const cold = await render({
      ...RADAR,
      data: RADAR.data.map((row) => ({ ...row, hits: 5 })),
    });

    expect(centre(hot)).toEqual(centre(cold));
  });
});
