/**
 * What a progress bar actually drew. `lib/progress.test.ts` has the sums; this
 * has the half that reaches the screen — the fill, the parts left out, and
 * which end the icon went to.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import type { ProgressPayload } from "@/lib/schemas/board";
import { Progress } from "@/components/board/items/progress";
import "@/i18n";

const BAR: ProgressPayload = {
  kind: "progress",
  value: 25,
  min: 0,
  max: 100,
  title: null,
  icon: null,
  icon_side: "start",
  min_label: null,
  max_label: null,
  color: null,
  unfilled: null,
};

const mounted: Root[] = [];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
  for (const root of mounted.splice(0)) act(() => root.unmount());
});

function draw(payload: ProgressPayload): HTMLElement {
  const host = document.createElement("div");
  const root = createRoot(host);
  mounted.push(root);
  act(() => root.render(<Progress id="p" payload={payload} />));
  return host;
}

describe("Progress", () => {
  it("fills the bar to the value in the colour asked for", () => {
    const host = draw({ ...BAR, color: "var(--color-success)" });
    const fill = host.querySelector<HTMLElement>("[data-testid=progress-fill]");
    expect(fill?.style.width).toBe("25%");
    expect(fill?.style.backgroundColor).toBe("var(--color-success)");
  });

  it("draws only the parts it was given", () => {
    expect(draw(BAR).textContent).toBe("100");
    expect(draw({ ...BAR, title: "TRM", max_label: "" }).textContent).toBe(
      "TRM",
    );
  });

  it("puts the icon at the end when told to", () => {
    const host = draw({ ...BAR, icon: "rocket", icon_side: "end" });
    const row = host.firstElementChild;
    expect(row?.lastElementChild?.querySelector("svg")).not.toBeNull();
    expect(row?.firstElementChild?.querySelector("svg")).toBeNull();
  });
});
