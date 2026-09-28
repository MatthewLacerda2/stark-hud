/**
 * What a player says as the board stops drawing it (#196).
 *
 * A widget leaves the screen without leaving the board in two ordinary ways:
 * the board turns to another page, or the group it sits in folds. Either way
 * `onBoard(onPage(...))` drops it, the grid unmounts it, and whatever it says on
 * the way out becomes the record the server keeps. `idle` was that word, and
 * `idle` is in #112's finished set — so a film paused halfway was taken off the
 * board an hour after somebody looked at another page.
 *
 * So this mounts the real grid behind the real filters, turns the page or folds
 * the group, and reads what went to the server. jsdom plays nothing and paints
 * nothing, so the transport is stubbed and the departing widget's exit
 * animation is let run out on a fake clock.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import type { Item, MediaPayload, Payload } from "@/lib/schemas/board";
import { BoardGrid } from "@/components/board/board-grid";
import { onPage } from "@/lib/pages";
import { onBoard } from "@/lib/groups";
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

let sent: { url: string; body: Record<string, unknown> }[] = [];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };
  HTMLMediaElement.prototype.play = vi.fn(() => Promise.resolve());
  HTMLMediaElement.prototype.pause = vi.fn();
  globalThis.fetch = vi.fn((url: string, init?: RequestInit) => {
    sent.push({ url, body: JSON.parse(String(init?.body ?? "{}")) });
    return Promise.resolve(
      new Response("{}", { headers: { "Content-Type": "application/json" } }),
    );
  }) as unknown as typeof fetch;
});

beforeEach(() => {
  sent = [];
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

function item(
  id: string,
  payload: Payload,
  parent: string | null = null,
): Item {
  return {
    ...{ id, key: null, description: null, color: null, border: null },
    ...{ scale: null, flat: false, payload, playback: null },
    ...{ x: id === "film" ? 0 : 7, y: 0, w: 6, h: 6 },
    ...{ page: "films", parent_id: parent, created_at: "2026-09-01T00:00:00Z" },
  };
}

/** A film an hour into four, playing or paused as the board last said. */
function film(playing: boolean): MediaPayload {
  const track = { path: "/films/heat.mkv", youtube: null, title: "Heat" };
  return {
    ...{ kind: "media", index: 0, playing, loop: false, muted: false },
    ...{ maximised: false, captions: false, seconds: 3600, title: null },
    tracks: [
      { ...track, artist: null, album: null, stamp: "s1", kind: "video" },
    ],
  };
}

/** Draw `items` the way the board does, and hand back a way to redraw them. */
async function board(items: Item[], showing: string) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const draw = async (all: Item[], page: string) => {
    await act(async () => {
      root.render(
        <BoardGrid
          items={onBoard(onPage(all, page))}
          everything={all}
          notifications={[]}
          wakes={{}}
          reloads={{}}
          origins={[]}
          tape={NO_TAPE}
          bloom={NO_BLOOM}
          glass={false}
          cols={32}
          rows={18}
        />,
      );
    });
    // Long enough for anything leaving to finish going, and be unmounted.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
  };
  await draw(items, showing);
  return { draw, host, done: () => act(async () => root.unmount()) };
}

/** Everything the page told the server about the film after `since`. */
function said(since: number): unknown[] {
  return sent
    .slice(since)
    .filter((s) => s.url === "/api/v1/board/items/film/playback")
    .map((s) => s.body);
}

it("says nothing about a paused film when the board turns to another page", async () => {
  const items = [item("film", film(false))];
  const { draw, host, done } = await board(items, "films");
  expect(host.querySelector("video")).not.toBeNull();
  const before = sent.length;

  await draw(items, "notes");

  // It really was taken off the screen, not merely hidden...
  expect(host.querySelector("video")).toBeNull();
  // ...and the pause another browser may still be showing still stands.
  expect(said(before)).toEqual([]);
  await done();
});

it("says nothing about a paused film when its group folds", async () => {
  const group = (state: "open" | "folded") =>
    item("shelf", { kind: "group", state });
  const inside = item("film", film(false), "shelf");
  const { draw, host, done } = await board([group("open"), inside], "films");
  const before = sent.length;

  await draw([group("folded"), inside], "films");

  expect(host.querySelector("video")).toBeNull();
  expect(said(before)).toEqual([]);
  await done();
});

it("says a playing film is paused when the page turns, and not that it is idle", async () => {
  // The case the report on the way out was written for (#47): folded or turned
  // away mid-film, the sound stops while the board still says play, so the
  // server's own rule for a stale `playing` (#167) cannot see it. `paused` is
  // true of this browser and never finished; the page coming back plays it on.
  const items = [item("film", film(true))];
  const { draw, done } = await board(items, "films");
  const before = sent.length;

  await draw(items, "notes");

  // Twice in fact: the grid drops a leaving widget for one render before it
  // draws its exit as a ghost, so it unmounts, mounts and unmounts again.
  expect(said(before).at(-1)).toEqual({ state: "paused" });
  expect(said(before)).not.toContainEqual({ state: "idle" });
  await done();
});
