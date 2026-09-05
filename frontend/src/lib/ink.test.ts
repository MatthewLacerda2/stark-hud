import { describe, expect, it } from "vitest";
import { inkVars } from "@/lib/ink";

describe("inkVars", () => {
  it("writes nothing when no ink is set, leaving the stylesheet's default", () => {
    expect(inkVars(null)).toEqual({});
  });

  it("sets what a widget writes in and what the board inherits", () => {
    expect(inkVars({ color: "var(--color-chart-2)" })).toEqual({
      "--color-foreground": "var(--color-chart-2)",
      "--color-card-foreground": "var(--color-chart-2)",
    });
  });

  it("leaves the muted colour alone, so a label stays dimmer than a reading", () => {
    expect(inkVars({ color: "var(--color-chart-2)" })).not.toHaveProperty(
      "--color-muted-foreground",
    );
  });
});
