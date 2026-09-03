/**
 * Dragging a widget, wired up rather than in the abstract.
 *
 * `drag.test.ts` covers the arithmetic and passed the whole time this was
 * broken, because the arithmetic was never wrong: a pointer landing on a resize
 * grip started the edge gesture and the event then bubbled to the widget
 * underneath, which replaced it with a move. Every grab became a drag and
 * resizing was not merely broken but unreachable.
 *
 * So this test drives the real elements — grip, window, pointer — and asserts
 * on what reached the server, which is the only place the two halves meet.
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

// 1920 by 1080 over 32 by 18 is exactly 60 pixels to a cell, so a pointer
// travelling 60px travels one column and every sum below is one a hand makes.
// Inlined because `vi.mock` is hoisted above anything this file declares.
vi.mock("@/hooks/use-container-size", () => ({
  useContainerSize: () => ({
    ref: { current: null },
    width: 1920,
    height: 1080,
  }),
}));

const mounted: Root[] = [];
let sent: { url: string; body: Record<string, number> }[] = [];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };
  globalThis.fetch = vi.fn((url: string, init?: { body?: string }) => {
    sent.push({ url, body: JSON.parse(init?.body ?? "{}") });
    return Promise.resolve(
      new Response("{}", { headers: { "Content-Type": "application/json" } }),
    );
  }) as unknown as typeof fetch;
});

afterEach(async () => {
  await act(async () => mounted.forEach((root) => root.unmount()));
  mounted.length = 0;
  sent = [];
});

function note(): Item {
  return {
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
    x: 4,
    y: 2,
    w: 8,
    h: 6,
    parent_id: null,
    pinned: false,
    created_at: "2026-09-01T00:00:00Z",
  };
}

/** jsdom has no PointerEvent; React only cares about the name and the coords. */
function pointer(
  type: string,
  x: number,
  y: number,
  altKey = false,
): MouseEvent {
  return new MouseEvent(type, {
    bubbles: true,
    clientX: x,
    clientY: y,
    button: 0,
    altKey,
  });
}

async function board() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);
  await act(async () => {
    root.render(
      <BoardGrid
        items={[note()]}
        everything={[note()]}
        notifications={[]}
        wakes={{}}
        tape={NO_TAPE}
        bloom={NO_BLOOM}
        cols={COLS}
        rows={ROWS}
      />,
    );
  });

  /** Grab something, drag by (dx, dy) pixels, and let go. */
  const drag = async (
    from: Element,
    dx: number,
    dy: number,
    altKey = false,
  ) => {
    await act(async () => from.dispatchEvent(pointer("pointerdown", 500, 500)));
    await act(async () =>
      window.dispatchEvent(pointer("pointermove", 500 + dx, 500 + dy, altKey)),
    );
    await act(async () => window.dispatchEvent(pointer("pointerup", 0, 0)));
  };

  return {
    drag,
    body: () => host.querySelector(".widget-surface") as Element,
    grip: (edge: string) =>
      host.querySelector(`.widget-grip-${edge}`) as Element,
    patched: () => sent.filter((s) => s.url.includes("/board/items/a")).at(-1),
  };
}

describe("a pointer on a resize grip", () => {
  it("resizes, and is not swallowed by the widget underneath it", async () => {
    const { drag, grip, patched } = await board();

    // The east edge, out by two columns. The widget is 60px to a cell here.
    await drag(grip("e"), 120, 0);

    expect(patched()?.body).toEqual({ x: 4, y: 2, w: 10, h: 6 });
  });

  it("moves the near edge and leaves the far one where it was", async () => {
    const { drag, grip, patched } = await board();

    await drag(grip("w"), -60, 0);

    expect(patched()?.body).toEqual({ x: 3, y: 2, w: 9, h: 6 });
  });

  it("takes both axes from a corner", async () => {
    const { drag, grip, patched } = await board();

    await drag(grip("se"), 60, 120);

    expect(patched()?.body).toEqual({ x: 4, y: 2, w: 9, h: 8 });
  });
});

describe("a pointer on the widget itself", () => {
  it("moves it, and changes nothing about its size", async () => {
    const { drag, body, patched } = await board();

    await drag(body(), 120, 60);

    expect(patched()?.body).toEqual({ x: 6, y: 3, w: 8, h: 6 });
  });

  it("lands where the pointer left it when no cell is near", async () => {
    // Half a cell out on both axes: nothing to be pulled onto, so the widget
    // keeps the decimals. This is the whole reason the coordinates are floats.
    const { drag, body, patched } = await board();

    await drag(body(), 30, 30);

    expect(patched()?.body).toEqual({ x: 4.5, y: 2.5, w: 8, h: 6 });
  });

  it("is pulled onto a whole cell when it comes close to one", async () => {
    const { drag, body, patched } = await board();

    // A cell and a half a magnet's width past it: near enough to be tidied.
    await drag(body(), 66, 0);

    expect(patched()?.body).toEqual({ x: 5, y: 2, w: 8, h: 6 });
  });

  it("is not pulled at all while the modifier is held", async () => {
    const { drag, body, patched } = await board();

    await drag(body(), 66, 0, true);

    expect(patched()?.body).toEqual({ x: 5.1, y: 2, w: 8, h: 6 });
  });
});
