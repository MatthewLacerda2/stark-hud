/**
 * The brand marks, which are the only glyphs this project draws itself.
 *
 * lucide has no brand icons, so `github` and `claude` are hand-carried paths
 * rather than an import. That makes them the two names that can silently go
 * missing from the set — a wrong import elsewhere is a build error, a name
 * dropped from `NAMED` just draws nothing. So this checks they are still there
 * and still render a path.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeAll, describe, expect, it } from "vitest";
import { Icon, NAMED } from "@/components/board/icon";

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
});

function draw(name: string): HTMLElement {
  const host = document.createElement("div");
  document.body.append(host);
  act(() => {
    createRoot(host).render(<Icon name={name} />);
  });
  return host;
}

describe("the marks we draw ourselves", () => {
  it("knows the brand names the backend accepts", () => {
    expect(Object.keys(NAMED)).toEqual(
      expect.arrayContaining(["github", "claude"]),
    );
  });

  it.each(["github", "claude"])("draws %s as a path", (name) => {
    const svg = draw(name).querySelector("svg");
    expect(svg?.getAttribute("fill")).toBe("currentColor");
    expect(svg?.getAttribute("viewBox")).toBe("0 0 24 24");
    expect(svg?.querySelector("path")?.getAttribute("d")).toBeTruthy();
  });
});
