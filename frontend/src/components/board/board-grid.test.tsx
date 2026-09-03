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
    border: null,
    scale: null,
    payload,
    playback: null,
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
  layer: () => HTMLElement;
  frames: () => string[];
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
          everything={board(maximised)}
          notifications={[]}
          wakes={{}}
          tape={NO_TAPE}
          bloom={NO_BLOOM}
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
    // The layer over the board, found by the one thing only it has: it is the
    // only element on the board lifted above the grid.
    layer: () =>
      [...host.querySelectorAll("div")].find((d) =>
        d.className.split(/\s+/).includes("z-30"),
      ) as HTMLElement,
    // Every widget's own outer frame, which is where a corner radius lives.
    frames: () =>
      [...host.querySelectorAll("div")]
        .filter((d) => d.className.includes("widget-surface"))
        .map((d) => d.className),
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

/**
 * A film with the whole board takes the whole screen, to the pixel.
 *
 * It used to take 1892x1064 of a 1920x1080 television, because the layer it is
 * drawn in carried the same 8px the grid puts around every widget: 1904x1064 of
 * room, which a 16:9 picture then letterboxed itself inside. What was left was
 * 14 pixels of the background video down each side and 8 along the top and
 * bottom — the seam the board was reported for.
 *
 * jsdom measures nothing, so these ask for the two properties that decide the
 * measurement rather than the measurement itself: no padding around the layer,
 * and no radius on the frame inside it. Both are pinned because both had to go
 * for the picture to reach the edge, and either one coming back brings the seam
 * back with it.
 */
describe("a film takes the exact screen", () => {
  it("is drawn in a layer with no padding of its own", async () => {
    const { show, layer } = await grid();
    await show(true);

    expect(layer().className).toMatch(/\binset-0\b/);
    expect(layer().className).not.toMatch(/\bp-\d/);
  });

  it("has a ground of its own, for a film that is not 16:9", async () => {
    // A 2.39:1 film keeps its bars, which is the film's shape and not a bug.
    // They have to be black: the wallpaper behind this layer is paused while a
    // film plays, so without a ground the bars would be a frozen still of it.
    const { show, layer } = await grid();
    await show(true);

    expect(layer().className).toMatch(/\bbg-background\b/);
  });

  it("squares off the corners the grid had rounded", async () => {
    const { show, frames } = await grid();

    // One widget among many is told apart from the next by its corners.
    await show(false);
    expect(frames().every((c) => c.includes("rounded-xl"))).toBe(true);

    // With the whole screen there is no next widget, and a rounded corner is a
    // bite out of the film. The album still playing in its own slot keeps its.
    await show(true);
    const [slot, whole] = frames();
    expect(slot).toContain("rounded-xl");
    expect(whole).not.toContain("rounded-xl");
  });
});
