/**
 * The board's look, as the numbers somebody can turn.
 *
 * The URL has always been the dial — `?vhs=0.4&bloom=1` — because the person
 * judging the look is across a room from a television. A menu now turns the
 * same numbers, and what it turns is kept in this browser, so everybody who
 * opens the board sets it up for themselves and the television keeps its own.
 *
 * Both speak the same language: a query string. What the browser kept is read
 * first and the address is laid over it, so a number typed into the URL still
 * means what it always meant. Nothing here knows what a scanline is; each look
 * says which numbers it reads and what they mean when absent, and this only
 * reads, writes and keeps them.
 */

/** One number in the query string. */
export type Dial = {
  param: string;
  /** What the look uses when the URL does not say. */
  fallback: number;
  /** The most it may be turned up to. */
  ceiling: number;
};

/** One look: a master, and the parts it scales. */
export type DialGroup = {
  name: string;
  master: Dial;
  parts: Dial[];
};

/** What a dial reads right now: the URL's number, or the look's own default. */
export function dialValue(search: string, dial: Dial): number {
  const raw = new URLSearchParams(search).get(dial.param);
  const value = raw === null ? dial.fallback : Number(raw);
  return Number.isFinite(value)
    ? Math.min(dial.ceiling, Math.max(0, value))
    : dial.fallback;
}

/**
 * The query string with one dial turned.
 *
 * A dial turned back to its default leaves the URL, so the address stays the
 * short list of what was actually changed, and a default that moves later is
 * not held in place by a number somebody's menu happened to write.
 */
export function withDial(search: string, dial: Dial, value: number): string {
  const params = new URLSearchParams(search);
  if (value === dial.fallback) params.delete(dial.param);
  else params.set(dial.param, String(value));
  return queryOf(params);
}

/** The query string with these dials gone, and so back at their defaults. */
export function withoutDials(search: string, dials: Dial[]): string {
  const params = new URLSearchParams(search);
  for (const dial of dials) params.delete(dial.param);
  return queryOf(params);
}

/** Every dial in these looks, master first within each. */
export function dialsOf(groups: DialGroup[]): Dial[] {
  return groups.flatMap((group) => [group.master, ...group.parts]);
}

/**
 * What this browser kept, with the address laid over it.
 *
 * Only the dials are taken from either side, so neither a stray parameter in
 * the address nor an old key in storage becomes part of the look.
 */
export function lookFrom(kept: string, address: string, dials: Dial[]): string {
  const stored = new URLSearchParams(kept);
  const asked = new URLSearchParams(address);
  const look = new URLSearchParams();
  for (const { param } of dials) {
    const value = asked.get(param) ?? stored.get(param);
    if (value !== null) look.set(param, value);
  }
  return queryOf(look);
}

function queryOf(params: URLSearchParams): string {
  const query = params.toString();
  return query ? `?${query}` : "";
}
