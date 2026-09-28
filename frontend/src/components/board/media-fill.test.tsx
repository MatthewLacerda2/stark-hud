/**
 * The button a person fills a player with, down both of its paths.
 *
 * What is real here is the component, `lib/api/` and the requests they make;
 * what is fake is the far end. `fetch` answers the hand-over and a stand-in
 * `XMLHttpRequest` answers the upload, so a test can say exactly what the board
 * replied — including the refusals, which are the half worth pinning: the page
 * shows the server's own sentence and never re-checks a link itself.
 *
 * What this cannot prove is that the widget then plays. That happens when the
 * socket brings the new queue back, which is the widget's own business and is
 * covered in `media.test.tsx`; the route that builds the queue is covered in
 * `backend/tests/api/v1/test_hand_over.py`.
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
import { MediaFill } from "@/components/board/media-fill";
import "@/i18n";

const LINK = "https://youtu.be/QgH9sr7G13Q?si=share";

/** Every request the hand-over made, and what the board says to the next one. */
let sent: { url: string; method?: string; body: unknown }[] = [];
let reply: { status: number; body: object } = { status: 200, body: {} };
const mounted: Root[] = [];

/** As much of `XMLHttpRequest` as an upload touches. */
class FakeXhr {
  static last: FakeXhr | null = null;
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
  open(_method: string, url: string): void {
    this.url = url;
  }
  send(body: unknown): void {
    this.sent = body;
  }
  progress(loaded: number, total: number): void {
    this.upload.onprogress?.({
      lengthComputable: true,
      loaded,
      total,
    } as ProgressEvent);
  }
  answer(status: number, body: object): void {
    this.status = status;
    this.responseText = JSON.stringify(body);
    this.onload?.();
  }
}

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
});

beforeEach(() => {
  sent = [];
  reply = { status: 200, body: {} };
  FakeXhr.last = null;
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      sent.push({
        url,
        method: init?.method,
        body: JSON.parse(String(init?.body ?? "null")),
      });
      return Promise.resolve(
        new Response(JSON.stringify(reply.body), { status: reply.status }),
      );
    }),
  );
});

afterEach(async () => {
  await act(async () => mounted.forEach((root) => root.unmount()));
  mounted.length = 0;
  vi.unstubAllGlobals();
});

async function render(): Promise<HTMLElement> {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  mounted.push(root);
  await act(async () => root.render(<MediaFill id="w1" />));
  return host;
}

/** The control's outermost element, which is what hides and shows. */
function control(host: HTMLElement): HTMLElement {
  return host.firstElementChild as HTMLElement;
}

async function openIt(host: HTMLElement): Promise<void> {
  const button = host.querySelector<HTMLButtonElement>(
    '[aria-label="Put something on"]',
  );
  await act(async () => button?.click());
}

/** Type into a controlled field the way a person does, which React hears. */
async function type(host: HTMLElement, text: string): Promise<void> {
  const field = host.querySelector<HTMLInputElement>(
    '[aria-label="Paste a YouTube link"]',
  ) as HTMLInputElement;
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )?.set;
  await act(async () => {
    setter?.call(field, text);
    field.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function submit(host: HTMLElement): Promise<void> {
  await act(async () => {
    host.querySelector("form")?.requestSubmit();
  });
}

/** Hand the picker a file, as the browser's own dialog would. */
async function pick(host: HTMLElement, file: File): Promise<void> {
  const input = host.querySelector<HTMLInputElement>(
    'input[type="file"]',
  ) as HTMLInputElement;
  Object.defineProperty(input, "files", {
    configurable: true,
    value: [file],
  });
  await act(async () => {
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function alert(host: HTMLElement): string | null {
  return host.querySelector('[role="alert"]')?.textContent ?? null;
}

describe("at rest", () => {
  it("draws nothing until a pointer is over the widget", async () => {
    const host = await render();

    expect(control(host).className).toContain("opacity-0");
    expect(control(host).className).toContain("group-hover:opacity-100");
    expect(control(host).className).toContain("no-drag");
    expect(host.querySelector("form")).toBe(null);
  });
});

describe("a YouTube link", () => {
  it("goes to the board as pasted, and the form goes away", async () => {
    const host = await render();
    await openIt(host);
    await type(host, `  ${LINK} `);
    await submit(host);

    expect(sent).toEqual([
      {
        url: "/api/v1/board/items/w1/queue",
        method: "PUT",
        body: { youtube: LINK },
      },
    ]);
    expect(host.querySelector("form")).toBe(null);
  });

  it("that the board cannot read shows the board's own reason", async () => {
    const reason = "'https://vimeo.com/1' is not a YouTube link";
    reply = { status: 422, body: { detail: reason } };
    const host = await render();
    await openIt(host);
    await type(host, "https://vimeo.com/1");
    await submit(host);

    expect(sent).toHaveLength(1);
    expect(alert(host)).toBe(reason);
    // Still open, with what was typed, so it can be corrected.
    expect(
      host.querySelector<HTMLInputElement>("input:not([type])")?.value,
    ).toBe("https://vimeo.com/1");
  });
});

describe("a file", () => {
  it("shows how much has gone up, then hands the board its path", async () => {
    const film = new File(["pretend-a-film"], "Interstellar.mp4");
    const host = await render();
    await openIt(host);
    await pick(host, film);

    const xhr = FakeXhr.last as FakeXhr;
    expect(xhr.url).toBe("/api/v1/media/upload?name=Interstellar.mp4");
    expect(xhr.sent).toBe(film);
    // Visible while it goes, hovered or not: a film takes minutes.
    expect(control(host).className).not.toContain("opacity-0");

    await act(async () => xhr.progress(7, 14));
    const bar = host.querySelector('[role="progressbar"]');
    expect(bar?.getAttribute("aria-valuenow")).toBe("50");
    expect(bar?.textContent).toContain("50%");
    expect(sent).toEqual([]);

    await act(async () =>
      xhr.answer(201, { path: "/data/uploads/ab/Interstellar.mp4" }),
    );

    expect(sent).toEqual([
      {
        url: "/api/v1/board/items/w1/queue",
        method: "PUT",
        body: { path: "/data/uploads/ab/Interstellar.mp4" },
      },
    ]);
    expect(host.querySelector("form")).toBe(null);
    expect(control(host).className).toContain("opacity-0");
  });

  it("the board will not take shows why, and queues nothing", async () => {
    const host = await render();
    await openIt(host);
    await pick(host, new File(["plans"], "plans.txt"));
    const reason = "'plans.txt' is not an audio or video file";
    await act(async () =>
      (FakeXhr.last as FakeXhr).answer(415, { detail: reason }),
    );

    expect(alert(host)).toBe(reason);
    expect(sent).toEqual([]);
  });

  it("that never reached the board says so in words of our own", async () => {
    const host = await render();
    await openIt(host);
    await pick(host, new File(["x"], "f.mp4"));
    await act(async () => (FakeXhr.last as FakeXhr).onerror?.());

    expect(alert(host)).toBe("The board did not answer. Is it still up?");
  });
});
