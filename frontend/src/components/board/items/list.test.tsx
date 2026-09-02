/**
 * Who decides the colour of each part of a list, read back off what it drew.
 *
 * The whole feature is a precedence — an entry's own colour, then the widget's,
 * then nothing at all — and a precedence is the kind of thing that reads
 * correctly and renders wrong. So this mounts real lists and looks at the
 * colours that came out, including the case that must still look like nothing.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeAll, describe, expect, it } from "vitest";
import type { ListEntry, ListPayload } from "@/lib/schemas/board";
import { List } from "@/components/board/items/list";
import "@/i18n";

// Three colours, each written the way a caller sends it and again the way the
// DOM stores it. Having to spell out the second form is itself the proof that
// the alpha survived the trip: two of these are partly transparent, and stay so.
const HEADING = "#33ccffaa";
const HEADING_PAINTED = "rgba(51, 204, 255, 0.667)";
const ENTRIES = "#ff8800";
const ENTRIES_PAINTED = "rgb(255, 136, 0)";
const MINE = "#00ff8840";
const MINE_PAINTED = "rgba(0, 255, 136, 0.25)";
// What a part that was told nothing has: no declaration, so it inherits.
const NONE = "";

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  // Nothing is ever laid out in jsdom, but the scroller measures itself.
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

const PLAIN: ListPayload = {
  kind: "list",
  title: "todo",
  icon: null,
  items: ["bread"],
  empty: null,
  title_color: null,
  icon_color: null,
  item_color: null,
};

const ENTRY: ListEntry = {
  title: "milk",
  body: "the oat one",
  icon: "check",
  title_color: null,
  body_color: null,
  icon_color: null,
};

async function render(payload: ListPayload): Promise<HTMLElement> {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(<List id="abc" payload={payload} />);
  });
  return host;
}

/** The heading, the entry's title, its body: the things a colour lands on. */
function colours(host: HTMLElement): (string | undefined)[] {
  const parts = [host.querySelector("h3"), ...host.querySelectorAll("li p")];
  return parts.map((part) => (part as HTMLElement | null)?.style.color);
}

describe("a list that was told nothing about colour", () => {
  it("draws no colour at all, plain lines or rows", async () => {
    const plain = await render(PLAIN);
    const rows = await render({ ...PLAIN, items: [ENTRY] });

    // Not "the default colour" — no declaration anywhere, so every part keeps
    // inheriting whatever the widget is. This is the board people already have.
    expect(plain.querySelector("[style]")).toBe(null);
    expect(rows.querySelector("[style]")).toBe(null);
    expect(rows.querySelector("svg")).not.toBe(null);
  });
});

describe("the widget-wide colours", () => {
  it("paint the heading and everything under it, apart", async () => {
    const host = await render({
      ...PLAIN,
      items: [ENTRY],
      title_color: HEADING,
      item_color: ENTRIES,
    });

    expect(host.querySelector("h3")?.style.color).toBe(HEADING_PAINTED);
    const entries = host.querySelector<HTMLElement>(".flex-1");
    expect(entries?.style.color).toBe(ENTRIES_PAINTED);
    // The entries themselves say nothing, which is how they inherit that.
    expect([...host.querySelectorAll("li p")]).toHaveLength(2);
    expect(host.querySelector("li [style]")).toBe(null);
  });
});

describe("an entry that names its own colours", () => {
  it("beats the widget on its title, its body and its icon", async () => {
    const host = await render({
      ...PLAIN,
      items: [
        {
          ...ENTRY,
          title_color: MINE,
          body_color: MINE,
          icon_color: MINE,
        },
      ],
      title_color: HEADING,
      item_color: ENTRIES,
    });

    expect(colours(host)).toEqual([
      HEADING_PAINTED,
      MINE_PAINTED,
      MINE_PAINTED,
    ]);
    expect(host.querySelector<SVGElement>("li svg")?.style.color).toBe(
      MINE_PAINTED,
    );
  });

  it("leaves the parts it did not name to the widget", async () => {
    const host = await render({
      ...PLAIN,
      items: [{ ...ENTRY, body_color: MINE }],
      item_color: ENTRIES,
    });

    expect(colours(host)).toEqual([NONE, NONE, MINE_PAINTED]);
  });
});

describe("the widget's own icon", () => {
  it("is drawn beside the heading, in the heading's colour", async () => {
    const host = await render({
      ...PLAIN,
      icon: "rocket",
      title_color: HEADING,
    });

    const glyph = host.querySelector<SVGElement>("h3 svg");
    expect(glyph).not.toBe(null);
    // Saying nothing is how it takes the heading's colour, rather than a second
    // copy of it that could drift.
    expect(glyph?.style.color).toBe(NONE);
  });

  it("takes a colour of its own when it is given one", async () => {
    const host = await render({
      ...PLAIN,
      icon: "rocket",
      title_color: HEADING,
      icon_color: MINE,
    });

    expect(host.querySelector<SVGElement>("h3 svg")?.style.color).toBe(
      MINE_PAINTED,
    );
    expect(host.querySelector("h3")?.style.color).toBe(HEADING_PAINTED);
  });

  it("is not lost when the widget has no title to sit beside", async () => {
    const host = await render({ ...PLAIN, title: null, icon: "rocket" });

    expect(host.querySelector("h3 svg")).not.toBe(null);
  });
});
