/**
 * Whether this page is still running the code the server is serving.
 *
 * A deploy changes the bundle and every board already open goes on running the
 * one from before it. That is not a cosmetic staleness: `ItemView` switches on
 * `payload.kind`, so a widget of a kind that did not exist when the bundle was
 * built draws *nothing at all* — not a broken box, an absence. And the board is
 * a television with no keyboard, so nobody standing near it can reload it.
 *
 * The page works this out for itself. Nothing tells it to. There is no
 * `board.reload` event and no endpoint that reloads viewers: this board has no
 * authentication on purpose, and "anything on the wifi can reload every screen
 * in the flat, repeatedly" is a capability worth not creating.
 *
 * It also cannot loop. After reloading, the page is running the served bundle,
 * so the next check finds nothing to do.
 */

/** Vite writes one module script into `index.html`, and its name carries the hash. */
const MODULE =
  /<script\b[^>]*\btype=["']module["'][^>]*\bsrc=["']([^"']+)["']/i;

/**
 * The bundle this HTML asks for, or `null` if it names none.
 *
 * Pure, so the one thing that can actually be wrong here — the parsing — is
 * tested without a browser or a server.
 */
export function bundleIn(html: string): string | null {
  return MODULE.exec(html)?.[1] ?? null;
}

/** The bundle this page is running, as the document names it. */
export function bundleRunning(doc: Document = document): string | null {
  const tag = doc.querySelector<HTMLScriptElement>(
    'script[type="module"][src]',
  );
  // The attribute rather than `.src`, which the browser resolves to an
  // absolute URL and would never match the relative path in the HTML.
  return tag?.getAttribute("src") ?? null;
}

/**
 * Whether the server has moved on from what this page is running.
 *
 * Cautious in every uncertain direction: a failed fetch, an unreadable page or
 * a document that names no module all answer "not stale". Reloading a
 * television on a hunch is worse than leaving it a version behind, and the
 * question gets asked again on the next reconnection anyway.
 */
export async function stale(fetcher: typeof fetch = fetch): Promise<boolean> {
  const mine = bundleRunning();
  if (!mine) return false;
  try {
    const response = await fetcher("/", { cache: "no-store" });
    if (!response.ok) return false;
    const theirs = bundleIn(await response.text());
    return theirs !== null && theirs !== mine;
  } catch {
    return false;
  }
}
