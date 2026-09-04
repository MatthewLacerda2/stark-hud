/**
 * Whether a page is still running the code the server is serving.
 *
 * The parsing is the part that can be wrong — a regex over somebody else's
 * generated HTML — so it is tested on its own, without a browser or a server.
 * The caution is the other half: every uncertain answer has to be "not stale",
 * because reloading a television on a hunch is worse than being a version
 * behind, and the question is asked again on the next reconnection.
 */
import { describe, expect, it, vi } from "vitest";
import { bundleIn, stale } from "@/lib/freshness";

const INDEX = (bundle: string) => `<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="UTF-8" />
    <link rel="stylesheet" href="/assets/index-abc123.css" />
    <script type="module" crossorigin src="${bundle}"></script>
  </head>
  <body><div id="root"></div></body>
</html>`;

function serving(html: string | null, ok = true): typeof fetch {
  return vi.fn(() =>
    Promise.resolve(
      html === null
        ? Promise.reject(new Error("down"))
        : new Response(html, { status: ok ? 200 : 503 }),
    ),
  ) as unknown as typeof fetch;
}

/** Put a module script in the document, the way vite's index.html does. */
function running(bundle: string) {
  document.head.innerHTML = `<script type="module" src="${bundle}"></script>`;
}

describe("reading the bundle out of a page", () => {
  it("finds the module script vite wrote", () => {
    expect(bundleIn(INDEX("/assets/index-B4mrWb.js"))).toBe(
      "/assets/index-B4mrWb.js",
    );
  });

  it("is not fooled by the stylesheet above it", () => {
    expect(bundleIn(INDEX("/assets/index-B4mrWb.js"))).not.toContain(".css");
  });

  it("says nothing when there is no module script at all", () => {
    expect(bundleIn("<html><body>maintenance</body></html>")).toBe(null);
  });
});

describe("deciding whether to reload", () => {
  it("reloads when the served bundle has moved on", async () => {
    running("/assets/index-old.js");
    expect(await stale(serving(INDEX("/assets/index-new.js")))).toBe(true);
  });

  it("stays put when it is the same bundle", async () => {
    running("/assets/index-same.js");
    expect(await stale(serving(INDEX("/assets/index-same.js")))).toBe(false);
  });

  it("stays put when the server cannot be reached", async () => {
    running("/assets/index-old.js");
    expect(await stale(serving(null))).toBe(false);
  });

  it("stays put when the server answers with an error page", async () => {
    running("/assets/index-old.js");
    expect(await stale(serving(INDEX("/assets/index-new.js"), false))).toBe(
      false,
    );
  });

  it("stays put when what came back names no bundle", async () => {
    running("/assets/index-old.js");
    expect(await stale(serving("<html><body>hello</body></html>"))).toBe(false);
  });

  it("stays put when this page names no bundle of its own", async () => {
    // A page opened some other way has nothing to compare, and guessing would
    // put a television into a reload it can never get out of.
    document.head.innerHTML = "";
    expect(await stale(serving(INDEX("/assets/index-new.js")))).toBe(false);
  });
});
