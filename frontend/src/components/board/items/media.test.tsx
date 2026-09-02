/**
 * What the player draws at the size it was given, and what it says it is doing.
 *
 * The threshold is the whole of the first half: four cells is where a title and
 * a position stop being readable across a room, and under it the widget has to
 * become a picture without becoming silent. So this mounts real widgets at both
 * sizes and looks at what came out — including the element that is still there
 * when nothing is drawn around it.
 *
 * jsdom implements no media playback at all: `play` is not a function on its
 * `HTMLMediaElement` and no event ever fires by itself. So the transport is
 * stubbed and the events are dispatched by hand, which is the only honest way to
 * ask what the widget does when a file will not decode.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { MediaPayload } from "@/lib/schemas/board";
import { Media } from "@/components/board/items/media";
import "@/i18n";

const ALBUM = "/mnt/d_drive/Music/AC DC - Greatest Hell's Hits/CD1";

const played = vi.fn(() => Promise.resolve());
const paused = vi.fn();
let sent: { url: string; body: Record<string, unknown> }[] = [];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  HTMLMediaElement.prototype.play = played;
  HTMLMediaElement.prototype.pause = paused;
  globalThis.fetch = vi.fn((url: string, init?: RequestInit) => {
    sent.push({ url, body: JSON.parse(String(init?.body ?? "{}")) });
    return Promise.resolve(
      new Response("{}", { headers: { "Content-Type": "application/json" } }),
    );
  }) as unknown as typeof fetch;
});

beforeEach(() => {
  sent = [];
  played.mockClear();
  paused.mockClear();
});

function queue(tracks: number, over: Partial<MediaPayload> = {}): MediaPayload {
  return {
    kind: "media",
    tracks: Array.from({ length: tracks }, (_, n) => ({
      path: `${ALBUM}/${String(n + 1).padStart(2, "0")} - Track ${n + 1}.mp3`,
      title: `Track ${n + 1}`,
      kind: "audio" as const,
    })),
    index: 0,
    playing: true,
    loop: false,
    muted: false,
    maximised: false,
    title: "Greatest Hell's Hits",
    ...over,
  };
}

async function render(
  payload: MediaPayload,
  cols: number,
  rows: number,
): Promise<HTMLElement> {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(
      <Media id="widget-1" payload={payload} cols={cols} rows={rows} />,
    );
  });
  return host;
}

/** The one media element, which is what is actually playing. */
function player(host: HTMLElement): HTMLVideoElement {
  return host.querySelector("video") as HTMLVideoElement;
}

describe("a player big enough to read", () => {
  it("says what is playing and where in the queue it is", async () => {
    const host = await render(queue(19), 10, 6);

    expect(host.textContent).toContain("Track 1");
    expect(host.textContent).toContain("Greatest Hell's Hits");
    expect(host.textContent).toContain("1 of 19");
  });

  it("plays the track by the widget's id, never by its path", async () => {
    const host = await render(queue(19, { index: 2 }), 10, 6);

    expect(player(host).getAttribute("src")).toBe(
      "/api/v1/media/widget-1/track/2",
    );
    expect(host.innerHTML).not.toContain("AC DC");
    expect(played).toHaveBeenCalled();
  });

  it("shows the album art beside the tracks, and a symbol without one", async () => {
    const host = await render(queue(19), 10, 6);
    const art = host.querySelector("img") as HTMLImageElement;
    expect(art.getAttribute("src")).toBe("/api/v1/media/widget-1/track/0/art");

    await act(async () => {
      art.dispatchEvent(new Event("error", { bubbles: true }));
    });
    expect(host.querySelector("img")).toBe(null);
    expect(host.querySelector("svg")).not.toBe(null);
  });
});

describe("a player too small to read", () => {
  it("draws a thumbnail instead, on either axis", async () => {
    for (const [cols, rows] of [
      [3, 6],
      [10, 3],
    ]) {
      const host = await render(queue(19), cols, rows);
      expect(host.textContent).not.toContain("Track 1");
      expect(host.textContent).not.toContain("1 of 19");
      expect(host.querySelector("img")).not.toBe(null);
    }
  });

  it("keeps playing: small is not a way to ask for silence", async () => {
    const host = await render(queue(19), 3, 3);

    expect(player(host)).not.toBe(null);
    expect(played).toHaveBeenCalled();
  });
});

describe("what the widget says it is doing", () => {
  it("tells the server a track ended, which is what moves the queue on", async () => {
    const host = await render(queue(19), 10, 6);
    await act(async () => {
      player(host).dispatchEvent(new Event("ended"));
    });

    expect(sent.at(-1)).toEqual({
      url: "/api/v1/board/items/widget-1/playback",
      body: { state: "ended", track: 0 },
    });
  });

  it("names a codec it will not take, rather than going quiet", async () => {
    const host = await render(queue(19), 10, 6);
    const media = player(host);
    Object.defineProperty(media, "error", { value: { code: 3 } });
    await act(async () => {
      media.dispatchEvent(new Event("error"));
    });

    expect(sent.at(-1)?.body).toEqual({
      state: "failed",
      track: 0,
      error: "decode",
    });
    expect(host.textContent).toContain("will not play");
  });

  it("has something honest to say with nothing queued", async () => {
    const host = await render(queue(0), 10, 6);

    expect(sent.at(-1)?.body).toEqual({ state: "idle" });
    expect(host.textContent).toContain("Nothing queued");
  });
});
