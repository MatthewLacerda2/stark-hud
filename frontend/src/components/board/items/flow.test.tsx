/**
 * What a flow widget actually draws.
 *
 * `lib/flow.test.ts` has the arithmetic. This has the half that #42 taught us
 * not to leave untested: that the sums reach the screen — a box per node, a
 * path per link, a head only where one was asked for, and a word that appears
 * only where there is room for it.
 *
 * jsdom lays nothing out, so the widget is handed a size by a `ResizeObserver`
 * that fires with one. What cannot be checked anywhere but on a television is
 * how any of it looks.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import type { FlowLink, FlowNode } from "@/lib/schemas/board";
import { Flow } from "@/components/board/items/flow";
import "@/i18n";

// A widget three cells tall and twelve wide, at roughly the television's scale.
const SIZE = { width: 720, height: 180 } as DOMRectReadOnly;

const mounted: Root[] = [];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.ResizeObserver = class {
    fire: ResizeObserverCallback;
    constructor(fire: ResizeObserverCallback) {
      this.fire = fire;
    }
    observe(target: Element) {
      this.fire(
        [{ target, contentRect: SIZE } as unknown as ResizeObserverEntry],
        this as unknown as ResizeObserver,
      );
    }
    unobserve() {}
    disconnect() {}
  };
});

afterEach(async () => {
  await act(async () => mounted.forEach((root) => root.unmount()));
  mounted.length = 0;
});

function node(id: string, over?: Partial<FlowNode>): FlowNode {
  return {
    id,
    text: id,
    shape: "rectangle",
    radius: 0.18,
    color: null,
    x: null,
    y: null,
    w: null,
    h: null,
    ...over,
  };
}

function link(
  source: string,
  target: string,
  over?: Partial<FlowLink>,
): FlowLink {
  return {
    source,
    target,
    source_side: null,
    target_side: null,
    label: null,
    curve: "straight",
    heads: "end",
    color: null,
    ...over,
  };
}

async function show(
  nodes: FlowNode[],
  links: FlowLink[],
  title: string | null = null,
) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);
  await act(async () => {
    root.render(
      <Flow
        id="w1"
        cols={12}
        rows={3}
        payload={{ kind: "flow", title, icon: null, nodes, links }}
      />,
    );
  });
  return {
    heading: () => host.querySelector("h3"),
    lines: () => [...host.querySelectorAll("path")],
    heads: () => [...host.querySelectorAll("polygon")],
    labels: () => [...host.querySelectorAll("text")].map((t) => t.textContent),
    text: () => host.textContent ?? "",
  };
}

const PIPELINE = [
  node("build", { text: "Build" }),
  node("ship", { text: "Ship" }),
];

describe("a flow", () => {
  it("draws a box per node and a line per link", async () => {
    const drawn = await show(PIPELINE, [link("build", "ship")]);

    expect(drawn.text()).toContain("Build");
    expect(drawn.text()).toContain("Ship");
    expect(drawn.lines()).toHaveLength(1);
  });

  it("draws no chrome at all when it was given no title and no icon", async () => {
    const drawn = await show(PIPELINE, [link("build", "ship")]);

    expect(drawn.heading()).toBeNull();
  });

  it("draws a heading when it was given one, the way a gantt does", async () => {
    const drawn = await show(PIPELINE, [], "Deploy");

    expect(drawn.heading()?.textContent).toContain("Deploy");
  });

  it("puts a head on the end alone, on both, or on neither", async () => {
    expect(
      (await show(PIPELINE, [link("build", "ship")])).heads(),
    ).toHaveLength(1);
    expect(
      (
        await show(PIPELINE, [link("build", "ship", { heads: "both" })])
      ).heads(),
    ).toHaveLength(2);
    // A plain connecting line is an arrow that points at nothing, which is why
    // there is no `line` kind of its own.
    expect(
      (
        await show(PIPELINE, [link("build", "ship", { heads: "none" })])
      ).heads(),
    ).toHaveLength(0);
  });

  it("writes a link's word on an arrow with room for it", async () => {
    const drawn = await show(PIPELINE, [
      link("build", "ship", { label: "ok" }),
    ]);

    expect(drawn.labels()).toEqual(["ok"]);
  });

  it("drops that word rather than laying it half over the line", async () => {
    // Nine ranks across twelve cells leaves each arrow well under a cell long.
    const many = Array.from({ length: 9 }, (_, at) => node(`n${at}`));
    const chain = many
      .slice(1)
      .map((to, at) => link(many[at].id, to.id, { label: "ok" }));
    const drawn = await show(many, chain);

    expect(drawn.labels()).toEqual([]);
    // The arrows themselves stay: it is the words that had nowhere to go.
    expect(drawn.lines()).toHaveLength(8);
  });

  it("says its empty line rather than drawing an empty pane", async () => {
    const drawn = await show([], []);

    expect(drawn.text()).toContain("Nothing to draw");
  });
});
