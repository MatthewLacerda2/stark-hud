/**
 * The rectangle a gesture draws, and the widget no longer jumping to it.
 *
 * `drag.test.ts` owns the arithmetic and is untouched by #168: the same three
 * outcomes, computed at the same moment on every pointer move. What changed is
 * what the answer is *used for*, and that is only visible with the elements on
 * the page — so this test holds the pointer down and reads the board mid
 * gesture, which `widget-drag.test.tsx` cannot do because its helper lets go in
 * the same breath.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { Item } from "@/lib/schemas/board";
import { BoardGrid } from "@/components/board/board-grid";
import { NO_TAPE } from "@/lib/vhs";
import { NO_BLOOM } from "@/lib/bloom";
import "@/i18n";

const COLS = 32;
const ROWS = 18;

// 1920 by 1080 over 32 by 18 is exactly 60 pixels to a cell, so every sum
// below is one a hand makes.
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
  globalThis.fetch = vi.fn(() =>
    Promise.resolve(
      new Response("{}", { headers: { "Content-Type": "application/json" } }),
    ),
  ) as unknown as typeof fetch;
});

afterEach(async () => {
  await act(async () => mounted.forEach((root) => root.unmount()));
  mounted.length = 0;
});

/** The widget every test drags. Eight by six, with its own id. */
function note(over: Partial<Item> = {}): Item {
  return {
    id: "a",
    key: null,
    description: null,
    color: null,
    border: null,
    scale: null,
    flat: false,
    payload: { kind: "note", text: "hello" },
    playback: null,
    x: 4,
    y: 2,
    w: 8,
    h: 6,
    page: "main",
    parent_id: null,
    created_at: "2026-09-01T00:00:00Z",
    ...over,
  };
}

/** A second widget, one column to the right of the first with a gap between. */
function neighbour(): Item {
  return note({ id: "b", x: 13, y: 2, w: 8, h: 6 });
}

function pointer(type: string, x: number, y: number): MouseEvent {
  return new MouseEvent(type, {
    bubbles: true,
    clientX: x,
    clientY: y,
    button: 0,
  });
}

/** The four percentages an element was placed at, read back as cells. */
function cells(element: Element | null): Record<string, number> | null {
  if (!element) return null;
  const style = (element as HTMLElement).style;
  const share = (value: string) => Number.parseFloat(value) / 100;
  return {
    x: Number((share(style.left) * COLS).toFixed(4)),
    y: Number((share(style.top) * ROWS).toFixed(4)),
    w: Number((share(style.width) * COLS).toFixed(4)),
    h: Number((share(style.height) * ROWS).toFixed(4)),
  };
}

/** The board, with the dragged widget first and whatever else is on it after. */
async function board(items: Item[] = [note()]) {
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
        glass={false}
        cols={COLS}
        rows={ROWS}
      />,
    );
  });

  const preview = () => host.querySelector(".drop-preview");
  const body = () => host.querySelector(".widget-edge") as Element;

  return {
    preview,
    body,
    grip: (edge: string) =>
      host.querySelector(`.widget-grip-${edge}`) as Element,
    /** Take hold of something and move the pointer, without letting go. */
    hold: async (from: Element, dx: number, dy: number) => {
      await act(async () =>
        from.dispatchEvent(pointer("pointerdown", 500, 500)),
      );
      await act(async () =>
        window.dispatchEvent(pointer("pointermove", 500 + dx, 500 + dy)),
      );
    },
    release: async () => {
      await act(async () => window.dispatchEvent(pointer("pointerup", 0, 0)));
    },
    /** The rectangle the preview is drawn at: its wrapper carries the frame. */
    landing: () => cells(preview()?.parentElement ?? null),
    /** The rectangle the widget itself is drawn at while it is held. */
    widget: () => cells(body().closest(".absolute")),
  };
}

describe("a widget being dragged", () => {
  it("draws nothing at all while nobody is holding one", async () => {
    const { preview } = await board([note(), neighbour()]);

    expect(preview()).toBeNull();
  });

  it("draws nothing for a pointer that went down and has not moved", async () => {
    const { body, preview } = await board([note(), neighbour()]);

    await act(async () =>
      body().dispatchEvent(pointer("pointerdown", 500, 500)),
    );

    expect(preview()).toBeNull();
  });

  it("follows the pointer instead of jumping to where it will land", async () => {
    // Two columns east puts a column of this widget inside the neighbour at 13.
    // #154 moved the widget itself back to 5 on this very pointer move — the
    // thing the owner reversed. It now stays under the hand at 6, and 5 is
    // what the rectangle shows.
    const { hold, body, widget, landing } = await board([note(), neighbour()]);

    await hold(body(), 120, 0);

    expect(widget()).toEqual({ x: 6, y: 2, w: 8, h: 6 });
    expect(landing()).toEqual({ x: 5, y: 2, w: 8, h: 6 });
  });

  it("shows the size it will land at, not the size it is", async () => {
    // A pocket three and a half columns wide — walls at 0..4 and 7.5..13 — and
    // a widget four wide carried into it from clear board. There is nowhere to
    // slide to, so it gives up half a column and lands three and a half wide,
    // in the same place the hand is holding it. This is the whole reason the
    // rectangle exists: nobody predicts that half column by eye.
    const { hold, body, widget, landing, preview } = await board([
      note({ x: 14, y: 2, w: 4, h: 6 }),
      note({ id: "west", x: 0, y: 2, w: 4, h: 6 }),
      note({ id: "east", x: 7.5, y: 2, w: 5.5, h: 6 }),
    ]);

    // Ten columns west: the widget's own left edge arrives exactly on 4.
    await hold(body(), -600, 0);

    expect(widget()).toEqual({ x: 4, y: 2, w: 4, h: 6 });
    expect(landing()).toEqual({ x: 4, y: 2, w: 3.5, h: 6 });
    expect(preview()?.className).toContain("drop-preview-fits");
  });

  it("shows the seat it is going back to when the drop is refused", async () => {
    // Eight columns east is most of this widget inside the other one, which is
    // the one case that should feel like a refusal. The rectangle answers the
    // same question it always answers — where this widget will be when the
    // hand opens — and here the answer is where it came from.
    const { hold, body, landing, preview } = await board([note(), neighbour()]);

    await hold(body(), 480, 0);

    expect(landing()).toEqual({ x: 4, y: 2, w: 8, h: 6 });
    expect(preview()?.className).toContain("drop-preview-home");
    expect(preview()?.className).not.toContain("drop-preview-fits");
  });

  it("puts the widget where the rectangle was the moment the hand opens", async () => {
    // With the request left in flight, because that is the gap this closes.
    // The landing rectangle is applied on release rather than when the server
    // answers — otherwise the widget hangs off the pointer for a round trip
    // and then jumps, which is the jump this issue took out of the drag.
    const answering = globalThis.fetch;
    globalThis.fetch = vi.fn(
      () => new Promise<Response>(() => {}),
    ) as unknown as typeof fetch;
    try {
      const { hold, release, body, widget, preview } = await board([
        note(),
        neighbour(),
      ]);

      await hold(body(), 120, 0);
      await release();

      expect(widget()).toEqual({ x: 5, y: 2, w: 8, h: 6 });
      expect(preview()).toBeNull();
    } finally {
      globalThis.fetch = answering;
    }
  });
});

/**
 * A resize gets the rectangle too — the owner asked for both — but only the
 * half of it that does not fight the hand. Two of `landed`'s three outcomes
 * move the widget bodily, and a resize whose far edge moved would not be a
 * resize, so what an edge is shown is the rectangle it is asking for and
 * whether the board will take it.
 */
describe("a widget being resized", () => {
  it("shows the rectangle the edge is asking for", async () => {
    // One column east: the widget's own east edge arrives on 13, flush against
    // the neighbour and legal.
    const { hold, grip, landing, preview } = await board([note(), neighbour()]);

    await hold(grip("e"), 60, 0);

    expect(landing()).toEqual({ x: 4, y: 2, w: 9, h: 6 });
    expect(preview()?.className).toContain("drop-preview-fits");
  });

  it("says so before the hand opens when the edge has run into someone", async () => {
    // One column further and the edge is inside the neighbour. Nothing is sent
    // and the widget goes home, so home is what the rectangle shows.
    const { hold, grip, landing, preview } = await board([note(), neighbour()]);

    await hold(grip("e"), 120, 0);

    expect(landing()).toEqual({ x: 4, y: 2, w: 8, h: 6 });
    expect(preview()?.className).toContain("drop-preview-home");
  });
});
