/**
 * The URLs an element fetches, and the one thing that was actually broken.
 *
 * The shapes below are the same strings the widgets used to build by hand, so
 * this is the proof that moving them changed nothing. The last test is the
 * reason for moving them: `VITE_API_URL` used to carry the JSON away and leave
 * every picture pointing at whatever origin served the page.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
  vi.unstubAllGlobals();
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
    expect(backgroundUrl("ab12.mp4")).toBe(
      "/api/v1/media/background/ready?v=ab12.mp4",
    );
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

/**
 * The one request on this board that is not `fetch`: a file going up, which is
 * `XMLHttpRequest` because nothing else reports how much of a body has gone.
 * jsdom's own would try to reach a server, so this is the part of it the upload
 * touches, holding what it was sent and answering when a test says so.
 */
class FakeXhr {
  static last: FakeXhr | null = null;
  method = "";
  url = "";
  sent: unknown = null;
  status = 0;
  statusText = "";
  responseText = "";
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = {
    onprogress: null,
  };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor() {
    FakeXhr.last = this;
  }
  open(method: string, url: string): void {
    this.method = method;
    this.url = url;
  }
  send(body: unknown): void {
    this.sent = body;
  }
  /** Some of the body has gone. */
  progress(loaded: number, total: number): void {
    this.upload.onprogress?.({
      lengthComputable: true,
      loaded,
      total,
    } as ProgressEvent);
  }
  /** The server has answered. */
  answer(status: number, body: object): void {
    this.status = status;
    this.responseText = JSON.stringify(body);
    this.onload?.();
  }
}

describe("handing the board a file", () => {
  beforeEach(() => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
  });

  it("posts the file itself, with its name in the query", async () => {
    const file = new File(["bits"], "Cidade de Deus.mkv");

    const going = uploadTrack(file);
    const xhr = FakeXhr.last as FakeXhr;
    xhr.answer(201, {
      path: "/data/uploads/ab/f.mp4",
      name: "f.mp4",
      bytes: 4,
    });
    const got = await going;

    expect(xhr.url).toBe("/api/v1/media/upload?name=Cidade%20de%20Deus.mkv");
    expect(xhr.method).toBe("POST");
    // The file, not a string and not a form: anything else is the whole film
    // copied through memory on the way out.
    expect(xhr.sent).toBe(file);
    expect(got.path).toBe("/data/uploads/ab/f.mp4");
  });

  it("encodes a name that would otherwise be a second query parameter", async () => {
    const going = uploadTrack(new File(["x"], "a&b=c ../d.mp4"));
    const xhr = FakeXhr.last as FakeXhr;
    xhr.answer(201, {});
    await going;

    expect(xhr.url).toBe("/api/v1/media/upload?name=a%26b%3Dc%20..%2Fd.mp4");
  });

  it("says how much has gone while it goes", async () => {
    const heard: number[] = [];
    const going = uploadTrack(new File(["film"], "f.mp4"), (fraction) =>
      heard.push(fraction),
    );
    const xhr = FakeXhr.last as FakeXhr;
    xhr.progress(1, 4);
    xhr.progress(4, 4);
    xhr.answer(201, {});
    await going;

    expect(heard).toEqual([0.25, 1]);
  });

  it("carries the board's refusal the way every other call does", async () => {
    const going = uploadTrack(new File(["x"], "plans.txt"));
    (FakeXhr.last as FakeXhr).answer(415, {
      detail: "'plans.txt' is not an audio or video file",
    });

    await expect(going).rejects.toMatchObject({
      name: "ApiError",
      status: 415,
      message: "'plans.txt' is not an audio or video file",
    });
  });
});
