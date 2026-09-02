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

function draw(name: string, src?: string): HTMLElement {
  const host = document.createElement("div");
  document.body.append(host);
  act(() => {
    createRoot(host).render(<Icon name={name} src={src} />);
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

describe("the three forms an icon takes", () => {
  it("tells them apart by how they start", () => {
    expect(draw("cpu").querySelector("svg")).not.toBe(null);
    expect(
      draw("/home/me/face.png", "/api/v1/media/x/icon").querySelector("img"),
    ).not.toBe(null);
    // Markup comes from the backend already rebuilt from an allowlist — this
    // only has to draw it, and it is drawn inline so `currentColor` works.
    const markup = draw('<svg viewBox="0 0 24 24"><path d="M4 4h16"/></svg>');
    expect(markup.querySelector("svg > path")?.getAttribute("d")).toBe(
      "M4 4h16",
    );
  });
});
