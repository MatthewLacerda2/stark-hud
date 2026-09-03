/**
 * What a countdown widget actually draws.
 *
 * `countdown.test.ts` has the arithmetic. This has the half that #42 taught us
 * not to leave untested: that the sums reach the screen, in the right order,
 * with the right half of the range bright, and that a row too tall for the
 * widget is hidden whole rather than cut across the middle.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { Countdown as Entry } from "@/lib/schemas/board";
import { Countdown } from "@/components/board/items/countdown";
import "@/i18n";

const NOW = new Date("2026-09-04T12:00:00Z").getTime();
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;

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

function thing(title: string, startsIn: number, lasts?: number): Entry {
  return {
    title,
    icon: null,
    start: new Date(NOW + startsIn).toISOString(),
    end:
      lasts === undefined
        ? null
        : new Date(NOW + startsIn + lasts).toISOString(),
  };
}

async function show(items: Entry[], title: string | null = null) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);
  await act(async () => {
    root.render(
      <Countdown
        id="w1"
        payload={{ kind: "countdown", title, icon: null, items, empty: null }}
      />,
    );
  });
  return {
    rows: () => [...host.querySelectorAll("li")],
    titles: () =>
      [...host.querySelectorAll("li")].map(
        (li) => li.querySelector("p")?.textContent ?? "",
      ),
    text: () => host.textContent ?? "",
  };
}

describe("a countdown row", () => {
  it("draws the reading and the facts on one line", async () => {
    const { text } = await show([
      thing("Deploy window", 2 * HOUR + 15 * MINUTE, HOUR),
    ]);

    expect(text()).toContain("Deploy window");
    expect(text()).toContain("02:15");
    expect(text()).toContain("·");
    expect(text()).toContain("–");
  });

  it("drops the reading once it is over, and keeps the times", async () => {
    const { text } = await show([thing("Standup", -2 * HOUR, HOUR)]);

    expect(text()).toContain("Standup");
    expect(text()).not.toContain("·");
  });

  it("says nothing at all when there is nothing coming", async () => {
    const { rows, text } = await show([]);

    expect(rows()).toHaveLength(0);
    expect(text()).toContain("Nothing coming up");
  });
});

describe("which end of the range is bright", () => {
  it("is the start while the thing is still ahead", async () => {
    const { rows } = await show([thing("Deploy", HOUR, HOUR)]);
    const [start, , end] = [...rows()[0].querySelectorAll("p > span")].slice(
      -3,
    );

    expect(start.className).toContain("opacity-75");
    expect(end.className).toContain("opacity-40");
  });

  it("is the end once it has begun", async () => {
    const { rows } = await show([thing("Deploy", -MINUTE, HOUR)]);
    const [start, , end] = [...rows()[0].querySelectorAll("p > span")].slice(
      -3,
    );

    expect(start.className).toContain("opacity-40");
    expect(end.className).toContain("opacity-75");
  });
});

describe("the order on screen", () => {
  it("is happening, then ahead, then over", async () => {
    const { titles } = await show([
      thing("later", 2 * HOUR),
      thing("done", -2 * HOUR),
      thing("now", -MINUTE, HOUR),
    ]);

    expect(titles()).toEqual(["now", "later", "done"]);
  });
});

describe("a widget too short for its rows", () => {
  it("never takes a row out of the layout to hide it", async () => {
    // `display: none` would free the space that decided the row did not fit,
    // and the measurement would oscillate for as long as the widget was up.
    // The counting itself is asserted in `use-fitting.test.ts`, where the
    // geometry can be stated rather than measured — jsdom lays nothing out.
    const { rows } = await show([thing("a", HOUR), thing("b", 2 * HOUR)]);

    for (const row of rows()) {
      expect(row.className).not.toMatch(/\bhidden\b/);
    }
  });
});
