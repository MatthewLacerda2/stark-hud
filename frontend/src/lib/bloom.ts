/**
 * How much light a widget spills, part by part.
 *
 * Bloom is what a bright thing does to the air in front of a lens: the lit
 * parts of a picture bleed past their own edges, and that bleed is most of what
 * separates something that is *emitting* from something that is printed. A
 * dashboard on a television is meant to read as lit.
 *
 * One set of numbers for the whole board rather than a setting on each widget.
 * This is a property of the screen — of how the room sees it — not of any one
 * panel, the same way nobody sets the contrast of a single window on a monitor.
 *
 * Off unless asked for. A look that changes what the board has always shown
 * should be chosen, not inherited, so `?bloom=0.5` turns it on and no query
 * string leaves the board exactly as it was.
 *
 * Not part of the tape. The tape is a fault in a recording; bloom is a property
 * of light, and the two are judged separately — `?vhs=0&bloom=0.6` is a fair
 * question to ask the board, so turning one off must not turn the other off.
 */

export type Bloom = {
  /**
   * How far the light carries. Wide and faint is a room with haze in it; tight
   * is a clean lens. On its own it does not brighten anything.
   */
  spread: number;
  /**
   * How much light is added back. This is the one that is really the on
   * switch: at zero the blur is still computed and then contributes nothing.
   */
  glow: number;
  /**
   * How bright a pixel has to be before it spills at all.
   *
   * The only part the master does not scale, because it is a line and not an
   * amount. Scaling it down would drag the line towards zero and make *more*
   * of the board bloom as you asked for less of it, which is backwards. It is
   * also what keeps the glow off the panels: a dark widget on a dark board has
   * almost nothing above the line, so the light comes off the letters, the
   * rings and the icons, which are the parts that are actually lit.
   */
  cutoff: number;
};

/** No light at all: the board exactly as it was before any of this existed. */
export const NO_BLOOM: Bloom = { spread: 0, glow: 0, cutoff: 0.6 };

/**
 * What `?bloom=1` means: the settled look, not the loudest one available.
 *
 * Arrived at by putting it on the television and standing back, twice.
 *
 * Wide and hot was the first guess and it was wrong in a specific way: every
 * lit thing grew a halo big enough to touch its neighbour, the glows merged,
 * and the board read as a screen with something wrong with it rather than as a
 * screen that is on. The fault there was reach, not brightness — which is why
 * `spread` stays small here and does most of the work of keeping this honest.
 *
 * Too far the other way was wrong more quietly: with the cutoff high, only
 * near-white pixels qualified, so the letters — the thing anybody actually
 * looks at — stayed flat and the effect was something you had to go looking
 * for. The cutoff is the dial that decides how much of the board takes part,
 * and it belongs low enough to include type.
 *
 * So: the light reaches barely past its source, there is not much of it, and
 * the line is low enough that lit type is on the right side of it. Visible
 * without being looked at, which is the whole brief.
 *
 * These are the board owner's numbers, settled at the television. They landed
 * within a hair of the ones arrived at here from the other direction, which is
 * the sort of agreement worth writing down rather than averaging away.
 */
const FULL: Bloom = { spread: 0.6, glow: 0.7, cutoff: 0.7 };

/** The parts a master scales. `cutoff` is deliberately not among them. */
const SCALED = ["spread", "glow"] as const;

/**
 * What each part may be turned up to.
 *
 * `glow` is the odd one, and deliberately: it is a multiplier on light rather
 * than a fraction of something, and overdriving it is how a thing reads as
 * genuinely bright rather than merely pale. Games have always let this one past
 * one. `spread` is a fraction of REACH and `cutoff` is a brightness, and
 * neither means anything above one.
 */
const CEILING: Record<keyof Bloom, number> = { spread: 1, glow: 4, cutoff: 1 };

function amount(raw: string | null, fallback: number, ceiling: number): number {
  const value = raw === null ? fallback : Number(raw);
  return Number.isFinite(value)
    ? Math.min(ceiling, Math.max(0, value))
    : fallback;
}

/**
 * Read the look out of a query string.
 *
 * `?bloom=0.6` turns the whole thing on at six tenths, and any part can be
 * named on its own — `?bloom=1&spread=0.15` is a tight bright bloom, and
 * `?bloom=1&spread=1&glow=0.3` is a wide faint one. `?cutoff=0.3` lowers the
 * line so more of the board qualifies as lit.
 *
 * The URL is the dial on purpose. This is a television across the room from the
 * person judging it, and the alternative to a number they can type is a rebuild
 * for every guess.
 */
export function bloomFrom(search: string): Bloom {
  const asked = new URLSearchParams(search);
  const master = amount(asked.get("bloom"), 0, 1);
  const bloom = { ...NO_BLOOM };
  for (const part of SCALED) {
    bloom[part] = amount(asked.get(part), FULL[part], CEILING[part]) * master;
  }
  bloom.cutoff = amount(asked.get("cutoff"), FULL.cutoff, CEILING.cutoff);
  return bloom;
}

/** Whether there is any light to draw at all. */
export function lit(bloom: Bloom): boolean {
  return bloom.glow > 0 && bloom.spread > 0;
}
