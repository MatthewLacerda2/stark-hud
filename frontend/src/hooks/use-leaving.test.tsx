/**
 * Keeping a widget on screen for a moment after the board has dropped it.
 *
 * Removal is the one change with nothing left to animate: by the time the board
 * hears about it, the widget is not in `items` and there is nothing to draw
 * shrinking. This is the only piece of the motion that needs any state at all,
 * and it is state about the last two frames rather than about the board.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import type { Item } from "@/lib/schemas/board";
import { useLeaving } from "@/hooks/use-leaving";

const mounted: Root[] = [];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(async () => {
  await act(async () => mounted.forEach((root) => root.unmount()));
  mounted.length = 0;
});

function item(id: string): Item {
  return {
    id,
    key: null,
    description: null,
    opacity: null,
    background: null,
    color: null,
    border: null,
    scale: null,
    payload: { kind: "note", text: id, color: null },
    playback: null,
    x: 0,
    y: 0,
    w: 4,
    h: 3,
    parent_id: null,
    pinned: false,
    created_at: "2026-09-01T00:00:00Z",
  };
}

/** Drive the hook by hand, the way the board drives it. */
async function board() {
  let latest: ReturnType<typeof useLeaving>;
  function Probe({ items }: { items: Item[] }) {
    latest = useLeaving(items);
    return null;
  }
  const host = document.createElement("div");
  const root = createRoot(host);
  mounted.push(root);
  const show = async (items: Item[]) => {
    await act(async () => root.render(<Probe items={items} />));
  };
  return { show, get: () => latest };
}

describe("a widget that has gone", () => {
  it("is still drawn, and knows it is on its way out", async () => {
    const { show, get } = await board();
    await show([item("a"), item("b")]);
    await show([item("a")]);

    expect(get().drawn.map((i) => i.id)).toEqual(["a", "b"]);
    expect(get().leaving("b")).toBe(true);
    expect(get().leaving("a")).toBe(false);
  });

  it("is forgotten when its animation says it has finished", async () => {
    const { show, get } = await board();
    await show([item("a"), item("b")]);
    await show([item("a")]);
    await act(async () => get().forget("b"));

    expect(get().drawn.map((i) => i.id)).toEqual(["a"]);
  });

  it("is drawn once if it comes back before it was forgotten", async () => {
    // Folding a group and unfolding it a moment later is exactly this, and two
    // of the same widget on the television is worse than no animation at all.
    const { show, get } = await board();
    await show([item("a"), item("b")]);
    await show([item("a")]);
    await show([item("a"), item("b")]);

    expect(get().drawn.map((i) => i.id)).toEqual(["a", "b"]);
    expect(get().leaving("b")).toBe(false);
  });

  it("keeps the last thing the board knew about it", async () => {
    const { show, get } = await board();
    await show([{ ...item("a"), x: 12, y: 6 }]);
    await show([]);

    const ghost = get().drawn[0];
    expect([ghost.x, ghost.y]).toEqual([12, 6]);
  });
});
