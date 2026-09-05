import { describe, expect, it } from "vitest";
import { inkVars } from "@/lib/ink";

describe("inkVars", () => {
  it("writes nothing when no ink is set, leaving the stylesheet's default", () => {
    expect(inkVars(null)).toEqual({});
  });

  it("sets both spellings, because the two ways text is coloured differ", () => {
    expect(inkVars({ color: "var(--color-chart-2)" })).toEqual({
      // What Tailwind's own utilities compile to, `text-foreground` included.
      "--foreground": "var(--color-chart-2)",
      "--card-foreground": "var(--color-chart-2)",
      // What the hand-written `widget-text` utility reads, and unreachable
      // through the name above it.
      "--color-card-foreground": "var(--color-chart-2)",
    });
  });

  it("leaves the body's colour alone, which is outside the board anyway", () => {
    expect(inkVars({ color: "var(--color-chart-2)" })).not.toHaveProperty(
      "--color-foreground",
    );
  });

  it("leaves the muted colour alone, so a label stays dimmer than a reading", () => {
    expect(inkVars({ color: "var(--color-chart-2)" })).not.toHaveProperty(
      "--color-muted-foreground",
    );
  });
});
