/**
 * The call on the board, wired up rather than in the abstract.
 *
 * `origin.test.ts` covers where it goes. This covers the three things only the
 * real element can say: that it is drawn beside the widget it names and not
 * inside it, that it ends by itself, and that it never takes a pointer event —
 * which on a television is invisible and on the one screen with a mouse is the
 * difference between a widget you can drag and one you cannot.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { Item, Origin } from "@/lib/schemas/board";
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

const WIDGET: Item = {
  id: "a",
  key: null,
  description: null,
  opacity: null,
  background: null,
  color: null,
  border: null,
  scale: null,
  payload: { kind: "note", text: "hello", color: null },
  playback: null,
  x: 2,
  y: 4,
  w: 4,
  h: 4,
  parent_id: null,
  pinned: false,
  created_at: "2026-09-01T00:00:00Z",
};

const SAID: Origin = { id: "a", text: 'add_note(text="hello")' };

/** The board, with a way to find the call on it. */
async function board(items: Item[], origins: Origin[]) {
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
        origins={origins}
        tape={NO_TAPE}
        bloom={NO_BLOOM}
        cols={32}
        rows={18}
      />,
    );
  });

  const call = () => host.querySelector<HTMLElement>(".origin-call");
  return { host, call };
}

describe("the call that made a widget", () => {
  it("is drawn beside the widget and not inside it", async () => {
    const { host, call } = await board([WIDGET], [SAID]);
    const panel = call() as HTMLElement;

    expect(panel.textContent).toBe('add_note(text="hello")');
    // Six columns of thirty-two: the widget ends at column six, and the call
    // starts there rather than anywhere inside it.
    expect(panel.style.left).toBe("18.75%");
    expect(panel.style.width).toBe("25%");
    // Not a child of the widget: it is over the board, so nothing it does can
    // change what a widget is given to draw in.
    const widget = [...host.querySelectorAll("div")].find((div) =>
      div.className.includes("widget-settle"),
    ) as HTMLElement;
    expect(widget.contains(panel)).toBe(false);
  });

  it("takes no pointer event, so the widget under it stays draggable", async () => {
    const { call } = await board([WIDGET], [SAID]);

    expect(call()?.className).toContain("pointer-events-none");
  });

  it("takes itself away, and never asks the board to", async () => {
    // Only `setTimeout` is faked: React's own scheduler uses the rest of the
    // clock, and a board that cannot finish rendering proves nothing.
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    try {
      const { call } = await board([WIDGET], [SAID]);
      expect(call()).not.toBeNull();

      await act(async () => {
        vi.advanceTimersByTime(2000);
      });

      expect(call()).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("draws nothing for a widget that is not there", async () => {
    // The board was cleared, or the widget removed, between the call being made
    // and this render. There is nothing left to sit beside, so nothing sits.
    const { call } = await board([], [SAID]);

    expect(call()).toBeNull();
  });
});
