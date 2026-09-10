/**
 * Reading a gantt: the window, the floor, the absence of a ceiling, and where a
 * bar lands in the frame.
 *
 * The clock is stated rather than read, so every one of these is a fact about
 * the arithmetic and not about when the suite happened to run.
 */
import { describe, expect, it } from "vitest";
import type { GanttRow } from "@/lib/schemas/board";
import { label, place, roomy, span, step, STEPS } from "@/lib/gantt";

const NOW = new Date("2026-09-04T18:00:00Z").getTime();
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

function bar(title: string, from: number, to: number) {
  return {
    title,
    start: new Date(NOW + from).toISOString(),
    end: new Date(NOW + to).toISOString(),
    color: null,
  };
}

/** The evening that motivated the issue: three things close, one far out. */
const EVENING: GanttRow[] = [
  {
    name: "Kitchen",
    bars: [
      bar("sauce", -10 * MINUTE, 25 * MINUTE),
      bar("bake", 40 * MINUTE, 58 * MINUTE),
    ],
  },
  { name: "Laundry", bars: [bar("wash", 15 * MINUTE, 45 * MINUTE)] },
  { name: "Film", bars: [bar("watch", 3 * HOUR, 4 * HOUR)] },
];

describe("the window", () => {
  it("is the smallest step covering the next few bars", () => {
    // Three things end inside the hour and the fourth is four hours out, which
    // is exactly what must not be allowed to crush tonight into a hairline.
    expect(span(EVENING, NOW)).toBe(HOUR);
  });

  it("widens once the near things are done, instead of staying zoomed in", () => {
    // Half an hour later the sauce is over; what is left is one thing in a
    // quarter of an hour and one thing three and a half hours out.
    expect(span(EVENING, NOW + 30 * MINUTE)).toBe(4 * HOUR);
  });

  it("never goes below five minutes", () => {
    const ending: GanttRow[] = [
      { name: "Kitchen", bars: [bar("sauce", -20 * MINUTE, 2 * MINUTE)] },
    ];

    expect(span(ending, NOW)).toBe(5 * MINUTE);
  });

  it("has no ceiling: three weeks out is a three-week window", () => {
    const far: GanttRow[] = [
      { name: "Trip", bars: [bar("flight", 20 * DAY, 21 * DAY)] },
    ];

    expect(span(far, NOW)).toBe(21 * DAY);
    expect(label(span(far, NOW))).toBe("3w");
  });

  it("keeps doubling past the last rung rather than clipping", () => {
    const last = STEPS[STEPS.length - 1];

    expect(step(last + 1)).toBe(2 * last);
    expect(step(5 * last)).toBe(8 * last);
  });

  it("falls back to the floor when nothing at all is ahead", () => {
    expect(
      span([{ name: "Kitchen", bars: [bar("sauce", -2 * HOUR, -HOUR)] }], NOW),
    ).toBe(5 * MINUTE);
  });
});

describe("the span mark", () => {
  it("says the frame in one short word", () => {
    expect(label(30 * MINUTE)).toBe("30m");
    expect(label(4 * HOUR)).toBe("4h");
    expect(label(3 * DAY)).toBe("3d");
    expect(label(14 * DAY)).toBe("2w");
  });
});

describe("where a bar lands", () => {
  it("clips a bar already running to the left edge", () => {
    // Not dropped, and not drawn backwards: starting at the edge is what says
    // this one has begun, and is why no "now" marker is needed.
    const running = bar("sauce", -20 * MINUTE, 10 * MINUTE);
    const slot = place(running, NOW, HOUR);

    expect(slot).toEqual({ offset: 0, width: 10 / 60 });
  });

  it("clips a bar running past the right edge the same way", () => {
    const slot = place(bar("film", 30 * MINUTE, 5 * HOUR), NOW, HOUR);

    expect(slot).toEqual({ offset: 0.5, width: 0.5 });
  });

  it("draws nothing for a bar that is over, or one wholly past the frame", () => {
    expect(place(bar("done", -2 * HOUR, -HOUR), NOW, HOUR)).toBeNull();
    expect(place(bar("later", 2 * HOUR, 3 * HOUR), NOW, HOUR)).toBeNull();
  });
});

describe("whether a bar can hold its own name", () => {
  it("says no to fifteen minutes of a four-hour window", () => {
    // 6% of the width. There is no font size at which "do the sauce" fits.
    expect(roomy(15 / 240, 12)).toBe(false);
  });

  it("says yes to the same fifteen minutes once the window is fifteen minutes", () => {
    expect(roomy(1, 12)).toBe(true);
  });

  it("asks the widget how wide it is, not only the bar", () => {
    // The same share of a widget four cells across is a fifth of the room.
    expect(roomy(0.5, 12)).toBe(true);
    expect(roomy(0.5, 4)).toBe(false);
  });
});
