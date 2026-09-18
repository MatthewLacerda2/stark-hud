/** The sums a progress bar draws from: how full, and what each end says. */
import { describe, expect, it } from "vitest";
import type { ProgressPayload } from "@/lib/schemas/board";
import { endLabel, filled } from "@/lib/progress";

const BAR = {
  kind: "progress",
  value: 25,
  min: 0,
  max: 100,
} as ProgressPayload;

describe("filled", () => {
  it("is the share of the way from min to max", () => {
    expect(filled({ ...BAR, value: 15, min: 10, max: 30 })).toBe(25);
  });

  it("draws a value past either end as empty or full", () => {
    expect(filled({ ...BAR, value: -5 })).toBe(0);
    expect(filled({ ...BAR, value: 130 })).toBe(100);
  });
});

describe("endLabel", () => {
  it("says nothing for a bar that starts from zero", () => {
    expect(endLabel(null, 0, true, "en")).toBe("");
  });

  it("names a near end that is not zero, and always the far one", () => {
    expect(endLabel(null, 10, true, "en")).toBe("10");
    expect(endLabel(null, 0, false, "en")).toBe("0");
  });

  it("writes a big number the short way", () => {
    expect(endLabel(null, 67_108_864, false, "en")).toBe("67.1M");
  });

  it("uses the text it was given, and an empty one hides the end", () => {
    expect(endLabel("Friday", 7, false, "en")).toBe("Friday");
    expect(endLabel("", 7, false, "en")).toBe("");
  });
});
