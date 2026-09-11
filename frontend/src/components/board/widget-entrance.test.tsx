/**
 * An arrival, wired up rather than in the abstract.
 *
 * `entrance.test.ts` covers the corridor arithmetic. This covers the three
 * things only the real element can say: that the class the board picks is the
 * one that reaches the widget, that the flight's start reaches it as a custom
 * property the keyframes can read, and — the one that would be a real bug — that
 * a panel rewritten on a schedule changes neither, so nothing restarts.
 *
 * A CSS animation runs on mount and the item's key does not change, so a
 * rewrite has never re-animated. What is new is that the animation's name and
 * its start are now computed from the board, and either of them changing under
 * a widget would restart it or move it mid-flight.
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

function note(
  id: string,
  rect: { x: number; y: number; w: number; h: number },
  text = id,
): Item {
  return {
    id,
    key: null,
    description: null,
    opacity: null,
    background: null,
    color: null,
    border: null,
    scale: null,
    payload: { kind: "note", text, color: null },
    playback: null,
    ...rect,
    parent_id: null,
    pinned: false,
    created_at: "2026-09-01T00:00:00Z",
  };
}

/** The board, and a way to find one widget's outer frame by what it says. */
async function board(items: Item[]) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);

  const show = async (shown: Item[]) => {
    await act(async () => {
      root.render(
        <BoardGrid
          items={shown}
          everything={shown}
          notifications={[]}
          wakes={{}}
          reloads={{}}
          tape={NO_TAPE}
          bloom={NO_BLOOM}
          cols={32}
          rows={18}
        />,
      );
    });
  };
  await show(items);

  // The frame is the element the motion class goes on: the only one carrying
  // the settle, which every widget has and nothing inside a widget does.
  const frame = (text: string): HTMLElement =>
    [...host.querySelectorAll("div")].find(
      (div) =>
        div.className.includes("widget-settle") &&
        (div.textContent ?? "").includes(text),
    ) as HTMLElement;

  return { show, frame };
}

describe("a widget arriving on the board", () => {
  it("flies in from its nearest clear edge, and says how far", async () => {
    const { frame } = await board([note("a", { x: 2, y: 5, w: 4, h: 4 })]);
    const widget = frame("a");

    expect(widget.className).toContain("widget-flying-in");
    // Six columns to the left wall is one and a half of its own four columns,
    // and a translate percentage is of the widget's own box.
    expect(widget.style.getPropertyValue("--fly-x")).toBe("-150.00%");
    expect(widget.style.getPropertyValue("--fly-y")).toBe("0.00%");
  });

  it("grows in place when every way out is over a neighbour", async () => {
    const { frame } = await board([
      note("middle", { x: 14, y: 7, w: 4, h: 4 }),
      note("west", { x: 5, y: 7, w: 2, h: 4 }),
      note("east", { x: 25, y: 7, w: 2, h: 4 }),
      note("north", { x: 14, y: 2, w: 4, h: 2 }),
      note("south", { x: 14, y: 15, w: 4, h: 2 }),
    ]);
    const widget = frame("middle");

    expect(widget.className).toContain("widget-arriving");
    expect(widget.className).not.toContain("widget-flying");
  });

  it("does not change its mind when the board fills in around it", async () => {
    // A widget flying in from the west, and then — inside the 700ms it takes —
    // four more widgets landing in every corridor it might have used. An
    // arrival is a fact about the moment it arrived: recomputed here, this one
    // would have no corridor left, and the class flipping from a flight to a
    // growth restarts the animation from nothing halfway across the board.
    const flyer = note("a", { x: 2, y: 5, w: 4, h: 4 });
    const { show, frame } = await board([flyer]);
    const widget = frame("a");
    const classes = widget.className;
    const style = widget.style.cssText;

    expect(classes).toContain("widget-flying-in");
    await show([
      flyer,
      note("west", { x: 0, y: 6, w: 2, h: 2 }),
      note("east", { x: 10, y: 6, w: 2, h: 2 }),
      note("north", { x: 3, y: 1, w: 2, h: 2 }),
      note("south", { x: 3, y: 11, w: 2, h: 2 }),
    ]);

    expect(frame("a")).toBe(widget);
    expect(widget.className).toBe(classes);
    expect(widget.style.cssText).toBe(style);
    // And the widgets that have just turned up are still asked, so this is one
    // answer kept rather than the question stopping being asked.
    expect(frame("west").style.getPropertyValue("--fly-x")).toBe("-100.00%");
  });

  it("leaves by a corridor clear of the board as it stands then", async () => {
    // It arrived from the west with nothing in the way. By the time it goes,
    // something is sitting in that corridor, so it goes out over the top —
    // which is only right if a departure is worked out when it departs.
    const going = note("a", { x: 2, y: 5, w: 4, h: 4 });
    const blocker = note("west", { x: 0, y: 6, w: 2, h: 2 });
    const { show, frame } = await board([going]);
    expect(frame("a").style.getPropertyValue("--fly-x")).toBe("-150.00%");

    await show([going, blocker]);
    await show([blocker]);
    const ghost = frame("a");

    expect(ghost.className).toContain("widget-flying-out");
    expect(ghost.style.getPropertyValue("--fly-x")).toBe("0.00%");
    // Nine rows to the top, over a widget four rows tall.
    expect(ghost.style.getPropertyValue("--fly-y")).toBe("-225.00%");
  });

  it("does not change under a panel that is rewritten", async () => {
    const { show, frame } = await board([
      note("panel", { x: 2, y: 5, w: 4, h: 4 }, "cold"),
    ]);
    const before = frame("cold");
    const classes = before.className;
    const style = before.style.cssText;

    // The same widget, five seconds later, with what the agent last wrote in
    // it. Same id, so the same element: nothing here may restart an animation.
    await show([note("panel", { x: 2, y: 5, w: 4, h: 4 }, "warm")]);
    const after = frame("warm");

    expect(after).toBe(before);
    expect(after.className).toBe(classes);
    expect(after.style.cssText).toBe(style);
  });
});
