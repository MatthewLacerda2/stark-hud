/**
 * A chart's marks copied back into its pane: there on a depth board, absent off
 * one, and following the chart when it changes — by whichever of the two routes
 * the change takes. A mark that moves is swapped into the copies that are
 * standing; anything else has the copies taken again whole.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeAll, describe, expect, it } from "vitest";
import { Extrusion } from "@/components/board/extrusion";

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
});

async function draw(deep: boolean, bars: number) {
  const host = document.createElement("div");
  if (deep) host.className = "depth-board";
  document.body.append(host);
  const root = createRoot(host);
  const render = async (count: number) => {
    await act(async () => {
      root.render(
        <Extrusion>
          <svg>
            {Array.from({ length: count }, (_, at) => (
              <rect key={at} data-mark />
            ))}
          </svg>
        </Extrusion>,
      );
    });
    // One frame for the copy to be taken.
    await act(async () => {
      await new Promise((done) => requestAnimationFrame(() => done(null)));
    });
  };
  await render(bars);
  return { host, render };
}

describe("a chart's marks run back into the pane", () => {
  it("lays copies behind the chart on a depth board", async () => {
    const { host } = await draw(true, 2);
    const copies = host.querySelectorAll(".extrude-copy");
    expect(copies.length).toBeGreaterThan(1);
    expect(copies[0].querySelectorAll("[data-mark]")).toHaveLength(2);
  });

  it("draws the chart and nothing more off one", async () => {
    const { host } = await draw(false, 2);
    expect(host.querySelectorAll(".extrude-copy")).toHaveLength(0);
    expect(host.querySelectorAll("[data-mark]")).toHaveLength(2);
  });

  it("follows the chart when it changes", async () => {
    const { host, render } = await draw(true, 2);
    await render(3);
    const copy = host.querySelector(".extrude-copy");
    expect(copy?.querySelectorAll("[data-mark]")).toHaveLength(3);
  });

  it("follows a mark that only moves, without taking the copy again", async () => {
    const host = document.createElement("div");
    host.className = "depth-board";
    document.body.append(host);
    const root = createRoot(host);
    const paint = async (filled: string) => {
      await act(async () => {
        root.render(
          <Extrusion>
            {/* The words a widget draws beside its mark, which a copy hides and
                which do not change here — and the mark itself, which does. That
                is the shape of a gauge moving to a new reading. */}
            <div data-scaffold>
              <span>RAM</span>
              <div data-extrude-mark>
                <div data-fill style={{ width: filled }} />
              </div>
            </div>
          </Extrusion>,
        );
      });
      await act(async () => {
        await new Promise((done) => requestAnimationFrame(() => done(null)));
      });
    };

    await paint("10%");
    const scaffold = host.querySelector(".extrude-copy [data-scaffold]");
    await paint("70%");

    const copies = host.querySelectorAll(".extrude-copy");
    expect(copies.length).toBeGreaterThan(1);
    for (const copy of copies)
      expect(copy.querySelector<HTMLElement>("[data-fill]")?.style.width).toBe(
        "70%",
      );
    // The same scaffold element, so the copy was not taken again around it.
    expect(host.querySelector(".extrude-copy [data-scaffold]")).toBe(scaffold);
  });
});
