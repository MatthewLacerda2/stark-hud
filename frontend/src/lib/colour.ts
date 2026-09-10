/**
 * What a colour arriving over the wire already says about itself.
 *
 * The board takes any CSS colour, and two widgets now wash one down so the
 * video behind still moves through it. A colour that states its own alpha has
 * already been told how see-through to be, and washing it again quietly makes
 * it a quarter of what was asked for — so the check lives here, once, rather
 * than once per widget that needs it.
 */

/** True when a colour states its own alpha, as `#rgba` or `#rrggbbaa` do. */
export function carriesAlpha(color: string): boolean {
  return /^#(?:[0-9a-f]{4}|[0-9a-f]{8})$/i.test(color);
}
