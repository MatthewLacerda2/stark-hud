/**
 * Reading a countdown: the bands, the order, the expiry and both strings.
 *
 * All of it is a function of two datetimes and the current time, so all of it
 * can be asserted without a browser. The rendering is tested separately — #42
 * is the standing lesson about testing the sums and leaving the wiring
 * untested, and both halves are covered here.
 */
import { describe, expect, it } from "vitest";
import type { Countdown } from "@/lib/schemas/board";
import {
  at,
  KEEP_MS,
  ordered,
  phaseOf,
  remaining,
  ticking,
} from "@/lib/countdown";

// A fixed "now" so nothing here depends on when it is run.
const NOW = new Date("2026-09-04T12:00:00Z").getTime();
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;

function thing(title: string, startsIn: number, lasts?: number): Countdown {
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

describe("which band a thing is in", () => {
  it("is ahead before it starts, happening during, and over after", () => {
    const window = thing("deploy", HOUR, HOUR);
    expect(phaseOf(window, NOW)).toBe("ahead");
    expect(phaseOf(window, NOW + 90 * MINUTE)).toBe("happening");
    expect(phaseOf(window, NOW + 3 * HOUR)).toBe("over");
  });

  it("treats a thing with no end as over the moment it starts", () => {
    const moment = thing("train", HOUR);
    expect(phaseOf(moment, NOW)).toBe("ahead");
    expect(phaseOf(moment, NOW + HOUR + 1)).toBe("over");
  });
});

describe("the order they are drawn in", () => {
  it("puts what is happening first, then what is next, then what is over", () => {
    const rows = ordered(
      [
        thing("later", 2 * HOUR),
        thing("done", -2 * HOUR),
        thing("now", -MINUTE, HOUR),
      ],
      NOW,
    );

    expect(rows.map((r) => r.title)).toEqual(["now", "later", "done"]);
  });

  it("leads with the nearest deadline, and the freshest of the finished", () => {
    const rows = ordered(
      [
        thing("soon", HOUR),
        thing("sooner", MINUTE),
        thing("old", -5 * HOUR),
        thing("just", -HOUR),
      ],
      NOW,
    );

    expect(rows.map((r) => r.title)).toEqual(["sooner", "soon", "just", "old"]);
  });

  it("stops drawing a thing twelve hours after it is over", () => {
    const kept = ordered([thing("recent", -KEEP_MS + MINUTE)], NOW);
    const gone = ordered([thing("ancient", -KEEP_MS - MINUTE)], NOW);

    expect(kept.map((r) => r.title)).toEqual(["recent"]);
    expect(gone).toEqual([]);
  });
});

describe("how long is left", () => {
  it("counts to the start, and to the end once it has begun", () => {
    const window = thing("deploy", 2 * HOUR + 15 * MINUTE, HOUR);
    expect(remaining(window, NOW)).toBe("02:15");
    // It runs 02:15 to 03:15. Half an hour in, half an hour of the window is
    // left — and what is counted is the window, not the wait, which is gone.
    expect(remaining(window, NOW + 2 * HOUR + 45 * MINUTE)).toBe("00:30");
  });

  it("counts seconds inside the last minute", () => {
    expect(remaining(thing("train", 47_000), NOW)).toBe("0:47");
    expect(remaining(thing("train", 61_000), NOW)).toBe("00:01");
  });

  it("says the days when it is more than one away", () => {
    expect(
      remaining(thing("release", 2 * 24 * HOUR + 3 * HOUR + 15 * MINUTE), NOW),
    ).toBe("2d 03:15");
  });

  it("has nothing to say once it is over, rather than saying zero", () => {
    expect(remaining(thing("gone", -HOUR), NOW)).toBe(null);
  });
});

describe("the cadence", () => {
  it("goes to seconds before the last minute, not at it", () => {
    // The slow tick is thirty seconds wide, so asking exactly at the minute
    // could arrive a tick late and the seconds would start short of sixty.
    expect(ticking([thing("train", 80_000)], NOW)).toBe(true);
    expect(ticking([thing("train", 5 * MINUTE)], NOW)).toBe(false);
  });

  it("stays slow for something already over", () => {
    expect(ticking([thing("gone", -HOUR)], NOW)).toBe(false);
  });
});

describe("writing a time", () => {
  it("gives only the clock when it is today", () => {
    expect(at(new Date(NOW + HOUR).toISOString(), NOW)).toMatch(/^\d\d:\d\d$/);
  });

  it("puts the day in front when it is not", () => {
    expect(at(new Date(NOW + 3 * 24 * HOUR).toISOString(), NOW)).toMatch(
      /^\w+ \d\d:\d\d$/,
    );
  });
});
