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
  uploadTrack,
} from "@/lib/api/media";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
  vi.restoreAllMocks();
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

describe("handing the board a file", () => {
  it("posts the file itself, with its name in the query", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          path: "/data/uploads/ab/f.mp4",
          name: "f.mp4",
          bytes: 4,
        }),
        { status: 201 },
      ),
    );
    const file = new File(["bits"], "Cidade de Deus.mkv");

    const got = await uploadTrack(file);

    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/media/upload?name=Cidade%20de%20Deus.mkv");
    expect(init.method).toBe("POST");
    // The file, not a string and not a form: anything else is the whole film
    // copied through memory on the way out.
    expect(init.body).toBe(file);
    expect(init.headers).toEqual({});
    expect(got.path).toBe("/data/uploads/ab/f.mp4");
  });

  it("encodes a name that would otherwise be a second query parameter", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}", { status: 201 }));

    await uploadTrack(new File(["x"], "a&b=c ../d.mp4"));

    const [url] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/media/upload?name=a%26b%3Dc%20..%2Fd.mp4");
  });
});
