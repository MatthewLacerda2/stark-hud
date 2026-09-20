/**
 * A widget asked to go without its pane, on a board that still has panes.
 *
 * The glass is a face and four walls drawn behind it (`slab.tsx`), and what a
 * person looking at the television calls a border is the lit rim of that face.
 * It is one of the few things about a widget that no other test would notice
 * going: it draws no text, answers no pointer, and a board with the panes
 * missing renders perfectly.
 *
 * The rule being pinned is that the two switches only ever subtract. The board
 * has one for the whole browser and a widget has one of its own, and neither
 * can put back what the other took — so `?glass=0` is still the flat board it
 * has always been, whatever any widget asks for.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { Item } from "@/lib/schemas/board";
import { BoardGrid } from "@/components/board/board-grid";
import { NO_TAPE } from "@/lib/vhs";
import { NO_BLOOM } from "@/lib/bloom";
import "@/i18n";

vi.mock("@/hooks/use-container-size", () => ({
  useContainerSize: () => ({
    ref: { current: null },
    width: 1920,
    height: 1080,
  }),
}));

const mounted: Root[] = [];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };
});

afterEach(async () => {
  await act(async () => mounted.forEach((root) => root.unmount()));
  mounted.length = 0;
});

function note(id: string, x: number, flat: boolean): Item {
  return {
    id,
    key: null,
    description: null,
    color: null,
    border: null,
    scale: null,
    flat,
    payload: { kind: "note", text: id },
    playback: null,
    x,
    y: 0,
    w: 6,
    h: 6,
    page: "main",
    parent_id: null,
    created_at: "2026-09-01T00:00:00Z",
  };
}

/** A pane and a widget that asked for none, side by side on one board. */
const BOTH = [note("pane", 0, false), note("bare", 7, true)];

async function board(items: Item[], glass: boolean) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);
  await act(async () => {
    root.render(
      <BoardGrid
        items={items}
        everything={items}
        notifications={[]}
        wakes={{}}
        reloads={{}}
        origins={[]}
        tape={NO_TAPE}
        bloom={NO_BLOOM}
        glass={glass}
        cols={32}
        rows={18}
      />,
    );
  });
  // Which widgets have a pane, by the face at the front of one. The walls go
  // with it — they are drawn by the same component and by nothing else.
  return (): string[] =>
    [...host.querySelectorAll(".glass-face")].map(
      (face) => face.parentElement?.textContent ?? "",
    );
}

describe("a widget that asked to go without its glass", () => {
  it("loses its pane while the widget beside it keeps one", async () => {
    const paned = await board(BOTH, true);

    expect(paned()).toEqual(["pane"]);
  });

  it("cannot ask its edge back from a board that is flat", async () => {
    // The browser-wide dial is off, so nothing has a pane — including the
    // widget that said nothing about it, which is the whole board as it was.
    const paned = await board(BOTH, false);

    expect(paned()).toEqual([]);
  });

  it("is the only thing that decides it, on a board with the glass on", async () => {
    const paned = await board([note("a", 0, false), note("b", 7, false)], true);

    expect(paned()).toEqual(["a", "b"]);
  });
});
