/**
 * The look menu: it lists every dial, shows what the board is drawing with, and
 * gets out of the way.
 *
 * And the one thing in it that is not this screen's look: adding an empty media
 * player to the board. `fetch` is the far end for those, so a test can say what
 * the board answered — including a full board saying no.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { LookMenu } from "@/components/board/look-menu";
import { BLOOM_DIALS } from "@/lib/bloom";
import { DEPTH_DIALS } from "@/lib/depth";
import { TAPE_DIALS } from "@/lib/vhs";
import "@/i18n";

const GROUPS = [TAPE_DIALS, BLOOM_DIALS, DEPTH_DIALS];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

function open(search: string, onClose = vi.fn()) {
  const host = document.createElement("div");
  document.body.append(host);
  act(() => {
    createRoot(host).render(
      <LookMenu
        at={{ x: 10, y: 10 }}
        groups={GROUPS}
        search={search}
        onTurn={vi.fn()}
        onReset={vi.fn()}
        onClose={onClose}
      />,
    );
  });
  return host;
}

describe("the look menu", () => {
  it("has a row for every dial of every look", () => {
    const rows = open("").querySelectorAll("label");
    const dials = GROUPS.reduce((n, group) => n + 1 + group.parts.length, 0);
    expect(rows).toHaveLength(dials);
  });

  it("shows what the board is actually drawing with", () => {
    const text = open("?bloom=0.6").textContent ?? "";
    expect(text).toContain("0.60");
  });

  it("shuts on Escape", () => {
    const onClose = vi.fn();
    open("", onClose);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("shuts on a press outside it, and not on one inside", () => {
    const onClose = vi.fn();
    const host = open("", onClose);
    act(() => {
      host
        .querySelector("label")!
        .dispatchEvent(new Event("pointerdown", { bubbles: true }));
    });
    expect(onClose).not.toHaveBeenCalled();
    act(() => {
      document.body.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    });
    expect(onClose).toHaveBeenCalled();
  });
});

describe("adding a player, which is for every screen", () => {
  /** Every request made, and what the board says to them. */
  let sent: { url: string; method?: string; body: Record<string, unknown> }[];

  function answer(status: number, body: object) {
    sent = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        sent.push({
          url,
          method: init?.method,
          body: JSON.parse(String(init?.body)),
        });
        return Promise.resolve(new Response(JSON.stringify(body), { status }));
      }),
    );
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function addButton(host: HTMLElement): HTMLButtonElement {
    return [...host.querySelectorAll("button")].find(
      (button) => button.textContent === "Add a media player",
    ) as HTMLButtonElement;
  }

  it("sits in a section of its own, apart from this screen's dials", () => {
    const host = open("");
    const every = host.querySelector('section[aria-label="Every screen"]');
    const mine = host.querySelector('section[aria-label="This screen"]');

    expect(every?.contains(addButton(host))).toBe(true);
    expect(every?.querySelectorAll("label")).toHaveLength(0);
    expect(mine?.contains(addButton(host))).toBe(false);
  });

  it("puts an empty 16:9 player wherever the board has room, and shuts", async () => {
    answer(201, {});
    const onClose = vi.fn();
    const host = open("", onClose);
    await act(async () => addButton(host).click());

    expect(sent).toHaveLength(1);
    const [{ url, method, body }] = sent;
    expect([url, method]).toEqual(["/api/v1/board/items", "POST"]);
    expect(body.payload).toMatchObject({ kind: "media", tracks: [] });
    expect([body.w, body.h]).toEqual([12, 6.75]);
    // The board chooses where: a person adding by hand is not placing it.
    expect(body).not.toHaveProperty("x");
    expect(body).not.toHaveProperty("y");
    expect(onClose).toHaveBeenCalled();
  });

  it("shows a full board's refusal as it came, and stays open", async () => {
    const reason =
      "No free 12x6.75 slot. The largest free area is 8x4 at (0, 14).";
    answer(409, { detail: reason });
    const onClose = vi.fn();
    const host = open("", onClose);
    await act(async () => addButton(host).click());

    expect(host.querySelector('[role="alert"]')?.textContent).toBe(reason);
    expect(onClose).not.toHaveBeenCalled();
  });
});
