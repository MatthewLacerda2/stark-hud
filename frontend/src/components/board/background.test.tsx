/**
 * The background stops while it cannot be seen, and carries on where it stopped.
 *
 * This is the measurement that started the change, written down as a test. Under
 * a maximised film the machine was decoding two 1080p videos and showing one:
 * `nvidia-smi` reported no hardware decode at all, Chromium sat at about 224% of
 * a core, and the load average was 6.25 on eight. One of those two streams was
 * the background, completely hidden behind the other.
 *
 * jsdom implements no media playback — `play` and `pause` are not functions on
 * its `HTMLMediaElement` and nothing ever plays by itself — so the transport here
 * is a flag the stubs move, which is also what stands in for autoplay.
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
import { Background } from "@/components/board/background";

/** Whether the element is running, and how far in. jsdom has neither. */
let playing = false;
let at = 0;
const played = vi.fn(() => {
  playing = true;
  return Promise.resolve();
});
const stopped = vi.fn(() => {
  playing = false;
});
const mounted: Root[] = [];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  Object.defineProperty(HTMLMediaElement.prototype, "paused", {
    configurable: true,
    get: () => !playing,
  });
  Object.defineProperty(HTMLMediaElement.prototype, "currentTime", {
    configurable: true,
    get: () => at,
    set: (seconds: number) => {
      at = seconds;
    },
  });
  HTMLMediaElement.prototype.play = played;
  HTMLMediaElement.prototype.pause = stopped;
});

beforeEach(() => {
  playing = false;
  at = 0;
  played.mockClear();
  stopped.mockClear();
});

afterEach(async () => {
  await act(async () => {
    mounted.forEach((root) => root.unmount());
  });
  mounted.length = 0;
});

/** One host that stays put, so a second render is a rerender and not a remount. */
async function board(): Promise<{
  show: (covered: boolean) => Promise<void>;
  video: () => HTMLVideoElement | null;
}> {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);
  const show = async (covered: boolean) => {
    await act(async () => {
      root.render(
        <Background
          background={{ path: "/mnt/d_drive/Video/rain.mp4", blur: true }}
          covered={covered}
        />,
      );
    });
  };
  return { show, video: () => host.querySelector("video") };
}

describe("a video nobody can see", () => {
  it("plays while the board is a grid of widgets", async () => {
    const { show, video } = await board();
    await show(false);

    expect(video()).not.toBe(null);
    expect(playing).toBe(true);
  });

  it("stops the moment a widget is given the whole board", async () => {
    const { show } = await board();
    await show(false);
    await show(true);

    expect(playing).toBe(false);
  });

  it("carries on from where it stopped, rather than starting the loop again", async () => {
    const { show, video } = await board();
    await show(false);
    at = 742;
    const element = video();

    await show(true);
    // The same element throughout: a remount would fetch the file afresh and
    // come back at zero, which is a flicker in the one place it would be seen.
    expect(video()).toBe(element);
    expect(at).toBe(742);

    await show(false);
    expect(video()).toBe(element);
    expect(playing).toBe(true);
    expect(at).toBe(742);
  });

  it("never starts when it is set while something is already maximised", async () => {
    const { show } = await board();
    await show(true);

    // Stopped outright rather than only left alone: the element arrives with
    // `autoplay` set and the browser is about to act on it, and pausing is what
    // takes that away. Pausing something already paused says nothing.
    expect(stopped).toHaveBeenCalled();
    expect(played).not.toHaveBeenCalled();
    expect(playing).toBe(false);
  });

  it("is not there at all when the board has no background", async () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    mounted.push(root);
    await act(async () => {
      root.render(<Background background={null} covered={false} />);
    });

    expect(host.querySelector("video")).toBe(null);
  });
});
