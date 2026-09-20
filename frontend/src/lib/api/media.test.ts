/**
 * The URLs an element fetches, and the one thing that was actually broken.
 *
 * The shapes below are the same strings the widgets used to build by hand, so
 * this is the proof that moving them changed nothing. The last test is the
 * reason for moving them: `VITE_API_URL` used to carry the JSON away and leave
 * every picture pointing at whatever origin served the page.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  backgroundUrl,
  iconUrl,
  mediaUrl,
  notificationIconUrl,
  trackUrl,
} from "@/lib/api/media";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("the URLs behind the board's pictures", () => {
  it("are exactly what the widgets used to write out", () => {
    expect(mediaUrl("w1")).toBe("/api/v1/media/w1");
    expect(iconUrl("w1")).toBe("/api/v1/media/w1/icon");
    expect(iconUrl("w1", 0)).toBe("/api/v1/media/w1/icon/0");
    expect(iconUrl("w1", 3)).toBe("/api/v1/media/w1/icon/3");
    expect(backgroundUrl()).toBe("/api/v1/media/background");
    expect(notificationIconUrl("n1")).toBe("/api/v1/notifications/n1/icon");
  });

  it("stamp a track so a replaced queue is not served from cache", () => {
    expect(trackUrl("w1", 2, null)).toBe("/api/v1/media/w1/track/2");
    expect(trackUrl("w1", 2, "t3")).toBe("/api/v1/media/w1/track/2?v=t3");
    expect(trackUrl("w1", 0, "t1", "/art")).toBe(
      "/api/v1/media/w1/track/0/art?v=t1",
    );
  });

  it("move with VITE_API_URL, which is the whole point of them", async () => {
    vi.stubEnv("VITE_API_URL", "http://box.lan:8000/api/v1");
    vi.resetModules();
    const moved = await import("@/lib/api/media");

    expect(moved.iconUrl("w1")).toBe(
      "http://box.lan:8000/api/v1/media/w1/icon",
    );
    expect(moved.backgroundUrl()).toBe(
      "http://box.lan:8000/api/v1/media/background",
    );
  });
});
