/**
 * What a table actually drew: the grid its two halves are laid on, and the
 * cells that landed in it.
 *
 * The one thing that can go quietly wrong here is alignment. The headings and
 * the rows are separate grids so the headings can stay put while the rows
 * scroll, and two grids only line up if neither is sized by what happens to be
 * inside it — so the column template is asserted on both, together.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeAll, describe, expect, it } from "vitest";
import type { TablePayload } from "@/lib/schemas/board";
import { Table } from "@/components/board/items/table";
import "@/i18n";

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
});

const USAGE: TablePayload = {
  kind: "table",
  title: null,
  icon: null,
  columns: [
    { key: "name", label: null, align: "left", width: 2 },
    { key: "cpu", label: null, align: "right", width: 1 },
    { key: "ram", label: "memory", align: "right", width: 1 },
  ],
  rows: [
    { name: "chromium", cpu: "23%", ram: "1.6 GB" },
    { name: "gnome-shell", cpu: "1%", ram: "180 MB" },
  ],
  empty: null,
  title_color: null,
  icon_color: null,
  row_color: null,
};

async function render(payload: TablePayload): Promise<HTMLElement> {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(<Table id="abc" payload={payload} />);
  });
  return host;
}

/** Every grid in the widget, in the order it was drawn: headings, then rows.
 *
 * By document order rather than by a selector per half. `:first-of-type` counts
 * within a parent, and the rows have a parent of their own — the scroller — so
 * each of them is the first of its type too.
 */
function grids(host: HTMLElement): HTMLElement[] {
  return [...host.querySelectorAll<HTMLElement>("div.grid")];
}

/** The text of each cell in one of those grids. */
function cells(grid: HTMLElement): (string | null)[] {
  return [...grid.querySelectorAll("span")].map((cell) => cell.textContent);
}

describe("the columns", () => {
  it("are laid out in shares, identically for the headings and every row", async () => {
    const host = await render(USAGE);

    // One template, three times over: had any of them been sized from its own
    // contents, the widest cell in a row would have shifted that row alone.
    expect(grids(host).map((grid) => grid.style.gridTemplateColumns)).toEqual([
      "2fr 1fr 1fr",
      "2fr 1fr 1fr",
      "2fr 1fr 1fr",
    ]);
  });

  it("are headed by their label, or by their key when they have none", async () => {
    const host = await render(USAGE);

    expect(cells(grids(host)[0])).toEqual(["name", "cpu", "memory"]);
  });
});

describe("the cells", () => {
  it("are drawn exactly as they arrived, units and all", async () => {
    const host = await render(USAGE);

    expect(host.textContent).toContain("1.6 GB");
    expect(host.textContent).toContain("23%");
  });

  it("are empty where the row says nothing, rather than breaking the row", async () => {
    // A collector that could not reach the GPU sends rows with no `ram` at all.
    const host = await render({
      ...USAGE,
      rows: [{ name: "chromium", cpu: "23%" }],
    });
    expect(cells(grids(host)[1])).toEqual(["chromium", "23%", ""]);
  });
});

describe("more rows than fit", () => {
  it("are all drawn into a box that clips, rather than into a scroller", async () => {
    const rows = Array.from({ length: 40 }, (_, n) => ({ name: `p${n}` }));
    const host = await render({ ...USAGE, rows });

    // Every row is rendered and the order is kept — which one is visible is the
    // height's business, not this component's. What must not happen is the list
    // creeping up and down: a panel that refreshes every few seconds and also
    // moves is something in the corner of the eye rather than something read.
    expect(grids(host)).toHaveLength(41);
    expect(host.querySelector(".overflow-hidden")).not.toBe(null);
    expect(host.querySelector("[style*='animation']")).toBe(null);
  });
});

describe("a table with no rows", () => {
  it("says so instead of drawing headings over nothing", async () => {
    const host = await render({ ...USAGE, rows: [], empty: "nada rodando" });

    expect(host.textContent).toBe("nada rodando");
    expect(grids(host)).toHaveLength(0);
  });
});
