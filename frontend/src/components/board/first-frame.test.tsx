/**
 * The first frame the television paints.
 *
 * The board's coordinates are fractions of a grid, so nothing can be drawn in
 * the right place until the grid is known, and the grid comes from the server.
 * This test holds `/board/status` open — the throttled network, without a
 * network — and checks the two things that used to go wrong while it was in
 * flight: a widget drawn on a guessed 12 by 8 board, and an arrival aimed by
 * that guess.
 *
 * It lives here rather than beside the page it renders because the router
 * plugin turns every file under `src/routes/` into a route, and a test is not
 * a page of this board.
 *
 * jsdom measures nothing, so the size the grid lays itself out in is stubbed,
 * and the socket is stubbed too: what this is about is the one fact that does
 * not arrive over it.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { BoardStatus, Item } from "@/lib/schemas/board";
import { BoardPage } from "@/routes/index";
import "@/i18n";

/** The board a widget is sitting on the whole time, whoever has been told. */
const GRID = { cols: 32, rows: 18 };

const held = vi.hoisted(() => ({
  /** Answers the status request, when the test decides the server has. */
  answer: undefined as ((status: BoardStatus) => void) | undefined,
}));

vi.mock("@/lib/api/board", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/board")>()),
  boardStatus: () =>
    new Promise<BoardStatus>((resolve) => {
      held.answer = resolve;
    }),
}));

/** One widget, already on the board, delivered the instant the page mounts. */
const NOTE: Item = {
  id: "a",
  key: null,
  description: null,
  color: null,
  border: null,
  scale: null,
  payload: { kind: "note", text: "twenty across" },
  playback: null,
  x: 20,
  y: 4,
  w: 4,
  h: 4,
  page: "main",
  parent_id: null,
  pinned: false,
  created_at: "2026-09-01T00:00:00Z",
};

vi.mock("@/hooks/use-board", () => ({
  useBoard: () => ({
    items: [NOTE],
    showing: "main",
    background: null,
    ink: null,
    notifications: [],
    wakes: {},
    reloads: {},
    spoken: [],
    origins: [],
    connected: true,
  }),
}));

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
  held.answer = undefined;
});

/** What the server says when it is finally allowed to. */
function status(): BoardStatus {
  return {
    showing: "main",
    pages: ["main"],
    ...GRID,
    cells_total: GRID.cols * GRID.rows,
    cells_used: NOTE.w * NOTE.h,
    cells_free: GRID.cols * GRID.rows - NOTE.w * NOTE.h,
    item_count: 1,
    largest_free_rect: null,
  };
}

/** The page, with the status request left hanging until `answered` is called. */
async function page() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);

  // One client for the life of the page, the way `main.tsx` has one for the
  // life of the tab. A fresh one per render throws the answer away and asks
  // again, which is a board that never learns its own size.
  const client = new QueryClient();
  await act(async () => {
    root.render(
      <QueryClientProvider client={client}>
        <BoardPage />
      </QueryClientProvider>,
    );
  });

  /** The element the board positions and animates: one per widget. */
  const widget = (): HTMLElement | undefined =>
    [...host.querySelectorAll("div")].find((div) =>
      div.className.includes("widget-settle"),
    );

  /** The server answers at last, and the board is drawn from what it said.
   *
   * Turns the loop until the widget is there rather than once: several sessions
   * may be running gates on this machine at the same time, and how many ticks a
   * resolved query takes to reach the DOM is a fact about how busy the box is.
   */
  const answered = async () => {
    await act(async () => held.answer?.(status()));
    for (let turns = 0; turns < 100 && !widget(); turns += 1) {
      await act(async () => {
        await new Promise((settle) => setTimeout(settle, 5));
      });
    }
  };

  return { host, widget, answered };
}

describe("the board before the server has said how big it is", () => {
  it("draws no widget at all rather than one in the wrong place", async () => {
    const { host, widget } = await page();

    expect(widget()).toBeUndefined();
    expect(host.textContent).not.toContain("twenty across");
  });

  it("places the first widget it draws on the real grid", async () => {
    const { widget, answered } = await page();
    await answered();

    // Twenty columns along a board of thirty-two. On the 12 by 8 fallback this
    // was 166.67%: a widget off the side of its own screen.
    expect(widget()?.style.left).toBe("62.5%");
    expect(widget()?.style.width).toBe("12.5%");
  });

  it("picks the side a widget flies in from with the real grid in hand", async () => {
    const { widget, answered } = await page();
    await answered();

    // Eight rows to the ceiling is the nearest clear corridor, and it is two of
    // the widget's own four rows. Measured against 12 columns instead, the east
    // corridor came out 12 - 20 = -8 wide: the nearest edge by arithmetic, and
    // a flight that started off the west side while playing the east animation.
    // That is the strangeness the entrance had, and it was decided on the first
    // render — so drawing nothing until now is what cures it.
    expect(widget()?.className).toContain("widget-flying-in");
    expect(widget()?.style.getPropertyValue("--fly-y")).toBe("-200.00%");
    expect(widget()?.style.getPropertyValue("--fly-x")).toBe("0.00%");
  });
});
