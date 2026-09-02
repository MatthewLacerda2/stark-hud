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
 *
 * It has no YouTube either, and there is deliberately no key here to reach the
 * real one, so YouTube's player is stubbed the same way: an object with the
 * handful of methods the widget calls, holding the handlers it registered where
 * a test can fire them.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { MediaPayload, MediaTrack } from "@/lib/schemas/board";
import type { YouTubePlayerOptions } from "@/lib/youtube";
import { Media } from "@/components/board/items/media";
import "@/i18n";

const ALBUM = "/mnt/d_drive/Music/AC DC - Greatest Hell's Hits/CD1";
const VIDEO = "QgH9sr7G13Q";

const played = vi.fn(() => Promise.resolve());
const paused = vi.fn();
let sent: { url: string; body: Record<string, unknown> }[] = [];
/** The player last built, for a test to talk to. A box, because a class may
 * not hand `this` straight to a variable. */
const built: { player: FakeYouTubePlayer | null } = { player: null };

/** YouTube's player, as much of it as this widget ever touches. */
class FakeYouTubePlayer {
  videoId: string;
  events: NonNullable<YouTubePlayerOptions["events"]>;
  did: string[] = [];
  state = -1;

  constructor(host: HTMLElement, options: YouTubePlayerOptions) {
    this.videoId = options.videoId;
    this.events = options.events ?? {};
    // The real API replaces the element it is given with an iframe, which is
    // the reason the widget hands it a node of its own to lose.
    host.replaceWith(document.createElement("iframe"));
    built.player = this;
    // The real player is not usable the moment it is constructed and says so a
    // beat later, which is the beat the widget waits for before touching it.
    queueMicrotask(() => this.events.onReady?.({ target: this, data: 0 }));
  }

  playVideo(): void {
    this.did.push("play");
    this.enter(1);
  }
  pauseVideo(): void {
    this.did.push("pause");
    this.enter(2);
  }
  mute(): void {}
  unMute(): void {}
  loadVideoById(options: { videoId: string }): void {
    this.videoId = options.videoId;
  }
  cueVideoById(options: { videoId: string }): void {
    this.videoId = options.videoId;
  }
  getCurrentTime(): number {
    return 0;
  }
  getVideoData(): { title?: string } {
    return { title: "Highway to Hell (live at Donington)" };
  }
  destroy(): void {}

  /** Move to a state, and say so — but only when it is a change, as YouTube does. */
  private enter(code: number): void {
    if (this.state === code) return;
    this.state = code;
    this.says(code);
  }

  /** The two things a test makes YouTube say for itself. */
  says(code: number): void {
    this.events.onStateChange?.({ target: this, data: code });
  }
  refuses(code: number): void {
    this.events.onError?.({ target: this, data: code });
  }
}

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  HTMLMediaElement.prototype.play = played;
  HTMLMediaElement.prototype.pause = paused;
  window.YT = { Player: FakeYouTubePlayer };
  globalThis.fetch = vi.fn((url: string, init?: RequestInit) => {
    sent.push({ url, body: JSON.parse(String(init?.body ?? "{}")) });
    return Promise.resolve(
      new Response("{}", { headers: { "Content-Type": "application/json" } }),
    );
  }) as unknown as typeof fetch;
});

beforeEach(() => {
  sent = [];
  built.player = null;
  played.mockClear();
  paused.mockClear();
});

/** A YouTube track as the server normalises it: an id and nothing else. */
function video(): MediaTrack {
  return { path: null, youtube: VIDEO, title: VIDEO, kind: "youtube" };
}

function queue(tracks: number, over: Partial<MediaPayload> = {}): MediaPayload {
  return {
    kind: "media",
    tracks: Array.from({ length: tracks }, (_, n) => ({
      path: `${ALBUM}/${String(n + 1).padStart(2, "0")} - Track ${n + 1}.mp3`,
      youtube: null,
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
  // The YouTube player is reached through a promise, even when it is already
  // there. One more turn and it has been built.
  await act(async () => {});
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

describe("a YouTube video is another kind of track", () => {
  it("hands it to YouTube's player, and never to the file element", async () => {
    const host = await render(queue(0, { tracks: [video()] }), 10, 6);

    expect(built.player?.videoId).toBe(VIDEO);
    // The one thing that must not happen: an element with no source being told
    // to play, which fails on nothing and reports a working video as broken.
    expect(player(host).getAttribute("src")).toBe(null);
    expect(built.player?.did).toContain("play");
  });

  it("shows what YouTube calls it, not eleven characters of id", async () => {
    const host = await render(queue(0, { tracks: [video()] }), 10, 6);

    expect(host.textContent).toContain("Highway to Hell (live at Donington)");
    expect(host.textContent).not.toContain(VIDEO);
  });

  it("tells the server a video ended, which is what moves the queue on", async () => {
    await render(queue(0, { tracks: [video()] }), 10, 6);
    await act(async () => {
      built.player?.says(0);
    });

    expect(sent.at(-1)).toEqual({
      url: "/api/v1/board/items/widget-1/playback",
      body: { state: "ended", track: 0 },
    });
  });

  it("says in words that the owner will not have it played here", async () => {
    const host = await render(queue(0, { tracks: [video()] }), 10, 6);
    await act(async () => {
      built.player?.refuses(150);
    });

    expect(sent.at(-1)?.body).toEqual({
      state: "failed",
      track: 0,
      error: "the owner does not allow this video to be played outside YouTube",
    });
    expect(host.textContent).toContain("will not play");
  });

  it("sits in a queue beside files, each played by what can play it", async () => {
    const mixed = queue(2);
    mixed.tracks.splice(1, 0, video());

    const files = await render({ ...mixed, index: 0 }, 10, 6);
    expect(player(files).getAttribute("src")).toBe(
      "/api/v1/media/widget-1/track/0",
    );
    expect(built.player).toBe(null);

    const watching = await render({ ...mixed, index: 1 }, 10, 6);
    expect(built.player?.videoId).toBe(VIDEO);
    expect(player(watching).getAttribute("src")).toBe(null);
    expect(sent.at(-1)).toEqual({
      url: "/api/v1/board/items/widget-1/playback",
      body: { state: "playing", track: 1 },
    });

    // The file element is emptied and stopped on the way to a video. What it
    // says about that is about the file it left, not about what is playing now.
    await act(async () => {
      player(watching).dispatchEvent(new Event("pause"));
    });
    expect(sent.at(-1)?.body).toEqual({ state: "playing", track: 1 });
  });

  it("keeps playing when it is too small to watch, and shows the thumbnail", async () => {
    const host = await render(queue(0, { tracks: [video()] }), 3, 3);

    expect(built.player?.did).toContain("play");
    expect(host.querySelector("img")?.getAttribute("src")).toBe(
      `https://i.ytimg.com/vi/${VIDEO}/hqdefault.jpg`,
    );
  });
});
