/**
 * What the board is still building while one widget covers all of it.
 *
 * The grid keeps every slot — nothing moves, and giving the room back is one
 * render — but almost nothing goes into them. A looping video widget behind an
 * opaque one was decoding frames for nobody, which is the same waste as the
 * background, one layer up.
 *
 * The player underneath is the exception this test exists to pin down. The board
 * this was measured on has an album playing in a corner while a film is watched,
 * and sound is not covered by anything: unmounting it would silence it, lose its
 * place, and send the server a `paused` it never asked for.
 *
 * jsdom measures nothing, so the size the grid lays itself out in is stubbed; it
 * implements no media playback either, so the transport is stubbed the way
 * `media.test.tsx` stubs it.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { Item, Payload } from "@/lib/schemas/board";
import { BoardGrid } from "@/components/board/board-grid";
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
  HTMLMediaElement.prototype.play = vi.fn(() => Promise.resolve());
  HTMLMediaElement.prototype.pause = vi.fn();
  globalThis.fetch = vi.fn(() =>
    Promise.resolve(
      new Response("{}", { headers: { "Content-Type": "application/json" } }),
    ),
  ) as unknown as typeof fetch;
});

afterEach(async () => {
  await act(async () => {
    mounted.forEach((root) => root.unmount());
  });
  mounted.length = 0;
});

function item(id: string, payload: Payload, x: number): Item {
  return {
    id,
    key: null,
    description: null,
    opacity: null,
    background: null,
    color: null,
    scale: null,
    payload,
    playback: null,
    page: 0,
    x,
    y: 0,
    w: 6,
    h: 6,
    parent_id: null,
    pinned: false,
    created_at: "2026-09-01T00:00:00Z",
  };
}

function track(title: string, kind: "audio" | "video") {
  return {
    path: `/mnt/d_drive/${title}`,
    youtube: null,
    title,
    artist: null,
    album: null,
    stamp: "s1",
    kind,
  };
}

function media(maximised: boolean, kind: "audio" | "video"): Payload {
  return {
    kind: "media",
    tracks: [track(kind, kind)],
    index: 0,
    playing: true,
    loop: false,
    muted: false,
    maximised,
    captions: false,
    seconds: 0,
    title: null,
  };
}

/** The board that was measured: a film, an album, a loop, and a sticky note. */
function board(maximised: boolean): Item[] {
  return [
    item("film", media(maximised, "video"), 0),
    item("song", media(false, "audio"), 7),
    item(
      "loop",
      {
        kind: "video",
        path: "/mnt/d_drive/loop.mp4",
        autoplay: true,
        loop: true,
        muted: true,
      },
      14,
    ),
    item("note", { kind: "note", text: "Buy milk", color: null }, 21),
  ];
}

async function grid(): Promise<{
  show: (maximised: boolean) => Promise<void>;
  sources: () => (string | null)[];
  text: () => string;
}> {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);
  const show = async (maximised: boolean) => {
    await act(async () => {
      root.render(
        <BoardGrid
          items={board(maximised)}
          notifications={[]}
          cols={32}
          rows={18}
        />,
      );
    });
    // The player reaches for its element through a promise, even when it is
    // already there. One more turn and everything has settled.
    await act(async () => {});
  };
  return {
    show,
    sources: () =>
      [...host.querySelectorAll("video")].map((v) => v.getAttribute("src")),
    text: () => host.textContent ?? "",
  };
}

describe("a widget with the whole board", () => {
  it("draws every widget while it is one grid among many", async () => {
    const { show, sources, text } = await grid();
    await show(false);

    expect(sources()).toEqual([
      "/api/v1/media/film/track/0?v=s1",
      "/api/v1/media/song/track/0?v=s1",
      "/api/v1/media/loop",
    ]);
    expect(text()).toContain("Buy milk");
  });

  it("stops building what it covers, and is drawn exactly once itself", async () => {
    const { show, sources, text } = await grid();
    await show(false);
    await show(true);

    // The film, once — in the layer over the board, not also in its own slot —
    // and the album, still mounted and still playing. The looping video and the
    // note are gone: nothing about them was visible, and the loop was decoding.
    expect(sources()).toEqual([
      "/api/v1/media/song/track/0?v=s1",
      "/api/v1/media/film/track/0?v=s1",
    ]);
    expect(text()).not.toContain("Buy milk");
  });

  it("puts everything back when the board is given away again", async () => {
    const { show, sources, text } = await grid();
    await show(true);
    await show(false);

    expect(sources()).toEqual([
      "/api/v1/media/film/track/0?v=s1",
      "/api/v1/media/song/track/0?v=s1",
      "/api/v1/media/loop",
    ]);
    expect(text()).toContain("Buy milk");
  });
});
