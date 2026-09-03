/**
 * What the player draws at the size it was given, and what it never draws.
 *
 * Two rules are the whole of this file. A video is video: no title over it, no
 * queue position under it, nothing but the picture — so most of what this asks
 * is what is *absent*. Audio has a still picture to sit on, so it gets the album
 * art with the track's title above and the artist and album below, which is what
 * the tags on the server are read for.
 *
 * The threshold is the other half: four cells is where a line of text stops
 * being readable across a room, and under it the widget has to become a picture
 * without becoming silent. So this mounts real widgets at both sizes and looks
 * at what came out — including the element that is still there when nothing is
 * drawn around it.
 *
 * jsdom implements no media playback at all: `play` is not a function on its
 * `HTMLMediaElement` and no event ever fires by itself. So the transport is
 * stubbed and the events are dispatched by hand, which is the only honest way to
 * ask what the widget does when a file will not decode. It has no fullscreen
 * either, and that is stubbed for the same reason.
 *
 * It has no YouTube, and there is deliberately no key here to reach the real
 * one, so YouTube's player is stubbed the same way: an object with the handful
 * of methods the widget calls, holding the options it was built with and the
 * handlers it registered where a test can read and fire them.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import type { MediaPayload, MediaTrack } from "@/lib/schemas/board";
import type { YouTubePlayerOptions } from "@/lib/youtube";
import { Media } from "@/components/board/items/media";
import "@/i18n";

const ALBUM = "/mnt/d_drive/Music/AC DC - Greatest Hell's Hits/CD1";
const VIDEO = "QgH9sr7G13Q";

/** Where the one media element is. jsdom has no clock, so this is the clock. */
let at = 0;
const played = vi.fn(() => Promise.resolve());
const paused = vi.fn();
/** Whatever was asked to fill the screen, in order. jsdom has no fullscreen. */
let filled: Element[] = [];
let sent: { url: string; body: Record<string, unknown> }[] = [];
/** The player last built, for a test to talk to. A box, because a class may
 * not hand `this` straight to a variable. */
const built: { player: FakeYouTubePlayer | null } = { player: null };
/** Every root this file has rendered, so each test can take its own down. */
const mounted: Root[] = [];

/** YouTube's player, as much of it as this widget ever touches. */
class FakeYouTubePlayer {
  videoId: string;
  vars: Record<string, number>;
  events: NonNullable<YouTubePlayerOptions["events"]>;
  did: string[] = [];
  state = -1;
  sought: number | null = null;

  constructor(host: HTMLElement, options: YouTubePlayerOptions) {
    this.videoId = options.videoId;
    this.vars = options.playerVars ?? {};
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
  volume = 100;
  setVolume(volume: number): void {
    this.volume = volume;
  }
  loadVideoById(options: { videoId: string }): void {
    this.videoId = options.videoId;
  }
  cueVideoById(options: { videoId: string }): void {
    this.videoId = options.videoId;
  }
  seekTo(seconds: number): void {
    this.sought = seconds;
  }
  getCurrentTime(): number {
    return this.sought ?? 0;
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
  Object.defineProperty(HTMLMediaElement.prototype, "currentTime", {
    configurable: true,
    get: () => at,
    set: (seconds: number) => {
      at = seconds;
    },
  });
  HTMLMediaElement.prototype.play = played;
  HTMLMediaElement.prototype.pause = paused;
  HTMLElement.prototype.requestFullscreen = function (this: HTMLElement) {
    filled.push(this);
    return Promise.resolve();
  };
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
  filled = [];
  at = 0;
});

// Every widget keeps a timer running while it plays. Left mounted, a test three
// describes further down would find one of them reporting into its own `sent`.
afterEach(async () => {
  await act(async () => {
    mounted.forEach((root) => root.unmount());
  });
  mounted.length = 0;
});

/** A YouTube track as the server normalises it: an id and nothing else. */
function video(): MediaTrack {
  return {
    path: null,
    youtube: VIDEO,
    title: VIDEO,
    artist: null,
    album: null,
    stamp: null,
    kind: "youtube",
  };
}

/** A local video file, which draws exactly as much chrome as a YouTube one. */
function film(): MediaTrack {
  return {
    path: "/mnt/d_drive/Video/Live at Donington.mp4",
    youtube: null,
    title: "Live at Donington",
    artist: "AC/DC",
    album: "Live at Donington",
    stamp: "f11m",
    kind: "video",
  };
}

function queue(tracks: number, over: Partial<MediaPayload> = {}): MediaPayload {
  return {
    kind: "media",
    tracks: Array.from({ length: tracks }, (_, n) => ({
      path: `${ALBUM}/${String(n + 1).padStart(2, "0")} - Track ${n + 1}.mp3`,
      youtube: null,
      title: `Track ${n + 1}`,
      artist: "ACDC",
      album: "Greatest Hell's Hits (CD1)",
      stamp: `t${n + 1}`,
      kind: "audio" as const,
    })),
    index: 0,
    playing: true,
    loop: false,
    muted: false,
    maximised: false,
    captions: false,
    seconds: 0,
    title: "Greatest Hell's Hits",
    ...over,
  };
}

async function render(
  payload: MediaPayload,
  cols: number,
  rows: number,
  // Where a widget had got to is kept per id and outlives one test, so a test
  // about position takes an id of its own rather than the shared one.
  id = "widget-1",
): Promise<HTMLElement> {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);
  await act(async () => {
    root.render(<Media id={id} payload={payload} cols={cols} rows={rows} />);
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

describe("audio is a record sleeve", () => {
  it("names the track, who is playing it, and what it came off", async () => {
    const host = await render(queue(19), 10, 6);

    expect(host.textContent).toContain("Track 1");
    expect(host.textContent).toContain("ACDC");
    expect(host.textContent).toContain("Greatest Hell's Hits (CD1)");
  });

  it("never says where in the queue it is", async () => {
    const host = await render(queue(19), 10, 6);

    expect(host.textContent).not.toContain("1 of 19");
    expect(host.textContent).not.toContain("19");
  });

  it("says what it can when the file carried no tags", async () => {
    const bare = queue(1);
    bare.tracks[0] = { ...bare.tracks[0], artist: null, album: null };
    const host = await render(bare, 10, 6);

    // The title it derived from the filename, and the album the queue was given
    // — never a label with nothing beside it, and never the word "Unknown".
    expect(host.textContent).toContain("Track 1");
    expect(host.textContent).toContain("Greatest Hell's Hits");
    expect(host.textContent).not.toContain("Unknown");
    expect(host.textContent).not.toContain("·");
  });

  it("plays the track by the widget's id, never by its path", async () => {
    const host = await render(queue(19, { index: 2 }), 10, 6);

    expect(player(host).getAttribute("src")).toBe(
      "/api/v1/media/widget-1/track/2?v=t3",
    );
    expect(host.innerHTML).not.toContain("AC DC");
    expect(played).toHaveBeenCalled();
  });

  it("shows the album art beside the tracks, and a symbol without one", async () => {
    const host = await render(queue(19), 10, 6);
    const art = host.querySelector("img") as HTMLImageElement;
    expect(art.getAttribute("src")).toBe(
      "/api/v1/media/widget-1/track/0/art?v=t1",
    );

    await act(async () => {
      art.dispatchEvent(new Event("error", { bubbles: true }));
    });
    expect(host.querySelector("img")).toBe(null);
    expect(host.querySelector("svg")).not.toBe(null);
  });
});

describe("a video is video and nothing else", () => {
  it("draws no title, no artist and no album over a local one", async () => {
    const host = await render(queue(0, { tracks: [film()] }), 10, 6);

    expect(host.textContent).toBe("");
    expect(player(host).getAttribute("src")).toBe(
      "/api/v1/media/widget-1/track/0?v=f11m",
    );
  });

  it("draws nothing over a YouTube one either, not even its refusal", async () => {
    const host = await render(queue(0, { tracks: [video()] }), 10, 6);
    await act(async () => {
      built.player?.refuses(150);
    });

    expect(host.textContent).toBe("");
    // It is not silent about it — it is silent on the television, and says so
    // to the only place that can do anything about it.
    expect(sent.at(-1)?.body).toEqual({
      state: "failed",
      track: 0,
      error: "the owner does not allow this video to be played outside YouTube",
    });
  });
});

describe("a player too small to read", () => {
  it("draws a thumbnail instead, on either axis", async () => {
    for (const [cols, rows] of [
      [3, 6],
      [10, 3],
    ]) {
      const host = await render(queue(19), cols, rows);
      expect(host.textContent).toBe("");
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

describe("where in a track the widget is", () => {
  it("goes where the board says a four-hour film had got to", async () => {
    // A page that has just loaded is at zero and the board is not. This is the
    // whole of what survives a reload and a container restart.
    await render(queue(19, { seconds: 11160 }), 10, 6, "widget-seek");

    expect(at).toBe(11160);
  });

  it("is not jogged by its own tick coming back round through the server", async () => {
    at = 300;
    await render(queue(19, { seconds: 296 }), 10, 6, "widget-lag");

    expect(at).toBe(300);
  });

  it("says where it has got to, every so often and never every frame", async () => {
    vi.useFakeTimers();
    try {
      const host = await render(queue(19), 10, 6, "widget-tick");
      at = 742;
      await act(async () => {
        player(host).dispatchEvent(new Event("timeupdate"));
      });
      // Nothing yet, and that is the point: `timeupdate` fires several times a
      // second, and every report is a write on the server and a broadcast to
      // every other browser looking at the board.
      expect(sent).toHaveLength(0);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(10_000);
      });
      expect(sent.at(-1)?.body).toEqual({
        state: "playing",
        track: 0,
        seconds: 742,
      });
    } finally {
      vi.useRealTimers();
    }
  });

  it("sends a YouTube video where the board says, and leaves it alone otherwise", async () => {
    await render(
      queue(0, { tracks: [video()], seconds: 900 }),
      10,
      6,
      "widget-tube",
    );
    expect(built.player?.sought).toBe(900);

    await render(queue(0, { tracks: [video()] }), 10, 6, "widget-tube-2");
    expect(built.player?.sought).toBe(null);
  });

  it("fetches a replaced queue from a new URL, not the one already cached", async () => {
    // Index 0 is a different file now behind an identical path, which is how a
    // `<video>` came to insist a film was as long as the song before it.
    const before = await render(queue(19), 10, 6);
    const after = queue(19);
    after.tracks[0] = { ...after.tracks[0], stamp: "elsewhere" };

    expect(player(before).getAttribute("src")).not.toBe(
      player(await render(after, 10, 6)).getAttribute("src"),
    );
  });
});

describe("fullscreen is the one thing a call cannot do", () => {
  it("gives a pointer a button, on a file and on YouTube alike", async () => {
    for (const track of [film(), video()]) {
      const host = await render(queue(0, { tracks: [track] }), 10, 6);
      const control = host.querySelector("button");

      expect(control?.getAttribute("aria-label")).toBe("Fullscreen");
      await act(async () => {
        control?.click();
      });
      // The whole widget, so a YouTube iframe and a `<video>` both come with it.
      expect(filled.at(-1)).toBe(host.firstElementChild);
    }
  });

  it("is not there at all when there is nothing to watch", async () => {
    const host = await render(queue(0), 10, 6);

    expect(host.querySelector("button")).toBe(null);
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

  it("starts with the captions off, and turns them on when asked", async () => {
    await render(queue(0, { tracks: [video()] }), 10, 6);
    expect(built.player?.vars.cc_load_policy).toBe(0);

    await render(queue(0, { tracks: [video()], captions: true }), 10, 6);
    expect(built.player?.vars.cc_load_policy).toBe(1);
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

  it("sits in a queue beside files, each played by what can play it", async () => {
    const mixed = queue(2);
    mixed.tracks.splice(1, 0, video());

    const files = await render({ ...mixed, index: 0 }, 10, 6);
    expect(player(files).getAttribute("src")).toBe(
      "/api/v1/media/widget-1/track/0?v=t1",
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
