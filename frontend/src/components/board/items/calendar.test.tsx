/**
 * What a calendar widget actually draws.
 *
 * `calendar.test.ts` has the arithmetic. This is the half that checks it
 * reaches the screen: the right column headings, every day present, and exactly
 * one of them in a box.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { Calendar } from "@/components/board/items/calendar";
import "@/i18n";

// A Thursday in a month that starts on a Tuesday, so the blanks, the box and
// the last day are all in play at once.
const NOW = new Date(2026, 8, 10, 12);

const mounted: Root[] = [];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(async () => {
  await act(async () => mounted.forEach((root) => root.unmount()));
  mounted.length = 0;
});

async function show() {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  mounted.push(root);
  await act(async () => root.render(<Calendar />));
  return host;
}

/** The cells that carry a box, which should only ever be today's. */
const boxed = (host: HTMLElement) =>
  [...host.querySelectorAll("span")].filter((el) => el.style.border !== "");

describe("Calendar", () => {
  it("heads seven columns, starting on Sunday", async () => {
    const host = await show();
    const heads = [...host.querySelectorAll("span")]
      .filter((el) => el.className.includes("text-center"))
      .map((el) => el.textContent);
    expect(heads).toHaveLength(7);
    expect(heads[0]).toBe("S");
  });

  it("draws every day of the month and nothing past it", async () => {
    const host = await show();
    const numbers = [...host.querySelectorAll("span")]
      .map((el) => el.textContent ?? "")
      .filter((text) => /^\d+$/.test(text));
    expect(numbers).toContain("1");
    expect(numbers).toContain("30");
    expect(numbers).not.toContain("31");
  });

  it("puts today in a box, and only today", async () => {
    const host = await show();
    const marked = boxed(host);
    expect(marked).toHaveLength(1);
    expect(marked[0].textContent).toBe("10");
  });

  it("draws no month name", async () => {
    // The widget is glanced at, not consulted. A header band would cost its
    // full height on a widget that is already a grid.
    const host = await show();
    expect(host.textContent).not.toMatch(/sep|setem/i);
  });
});
