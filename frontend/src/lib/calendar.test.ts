/**
 * The arithmetic a calendar is: where the 1st lands, and how many weeks it takes.
 *
 * `calendar.test.tsx` has the half that checks the sums reach the screen.
 */
import { describe, expect, it } from "vitest";
import { initials, monthOf } from "@/lib/calendar";

/** Midday, so no timezone this test runs in can push it onto another day. */
const noon = (year: number, month: number, day: number) =>
  new Date(year, month - 1, day, 12);

describe("monthOf", () => {
  it("pushes the 1st onto its own weekday with blanks", () => {
    // 1 September 2026 was a Tuesday: Sunday and Monday come before it.
    const { days } = monthOf(noon(2026, 9, 10));
    expect(days.slice(0, 3)).toEqual([null, null, 1]);
  });

  it("starts a Sunday month with no blanks at all", () => {
    // 1 October 2023 was a Sunday, which is the column this board starts in.
    const { days } = monthOf(noon(2023, 10, 15));
    expect(days[0]).toBe(1);
  });

  it("knows February is longer in a leap year", () => {
    expect(monthOf(noon(2024, 2, 10)).days.at(-1)).toBe(29);
    expect(monthOf(noon(2023, 2, 10)).days.at(-1)).toBe(28);
  });

  it("counts the weeks a month actually spans", () => {
    // Five for most, six when a long month starts late in the week: 1 December
    // 2023 was a Friday, so its 31 days need a sixth row to land in.
    expect(monthOf(noon(2023, 10, 15)).weeks).toBe(5);
    expect(monthOf(noon(2023, 12, 15)).weeks).toBe(6);
    expect(monthOf(noon(2025, 3, 15)).weeks).toBe(6);
  });

  it("draws no cell past the last day", () => {
    // No trailing blanks: the grid stops where the month does.
    const { days } = monthOf(noon(2023, 12, 15));
    expect(days).toHaveLength(5 + 31);
    expect(days.at(-1)).toBe(31);
  });

  it("gives every day of the month exactly one cell", () => {
    const { days } = monthOf(noon(2026, 9, 10));
    expect(days.filter((day) => day !== null)).toEqual(
      Array.from({ length: 30 }, (_, at) => at + 1),
    );
  });
});

describe("initials", () => {
  it("starts the week on Sunday", () => {
    expect(initials("en-GB")).toEqual(["S", "M", "T", "W", "T", "F", "S"]);
  });

  it("follows the board's language", () => {
    // The reason these are not a table in the repo: nobody has to write them.
    expect(initials("pt-BR")).toHaveLength(7);
    expect(initials("pt-BR")).not.toEqual(initials("en-GB"));
  });
});
