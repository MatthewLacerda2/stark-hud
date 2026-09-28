import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { cn, FONT_SIZES } from "@/lib/utils";

describe("cn", () => {
  it("keeps a size from the scale beside a colour", () => {
    expect(cn("text-h3 text-foreground")).toBe("text-h3 text-foreground");
    expect(cn("text-body", "text-muted-foreground")).toBe(
      "text-body text-muted-foreground",
    );
    expect(cn("text-node-sm text-destructive")).toBe(
      "text-node-sm text-destructive",
    );
  });

  it("still lets a later size override an earlier one", () => {
    expect(cn("text-h3 text-body")).toBe("text-body");
    expect(cn("text-node text-foreground", "text-caption")).toBe(
      "text-foreground text-caption",
    );
  });

  it("still lets a later colour override an earlier one", () => {
    expect(cn("text-h3 text-foreground text-destructive")).toBe(
      "text-h3 text-destructive",
    );
  });

  it("knows every size the stylesheet defines, and only those", () => {
    // The file itself, not a `?raw` import: the Tailwind plugin owns every
    // import of it. Sub-properties (`--text-h3--line-height`) are not sizes.
    const css = readFileSync("src/styles.css", "utf8");
    const defined = [...css.matchAll(/^\s*--text-([a-z0-9-]+?):/gm)]
      .map((match) => match[1])
      .filter((name) => !name.includes("--"));
    expect([...FONT_SIZES].sort()).toEqual([...new Set(defined)].sort());
  });
});
