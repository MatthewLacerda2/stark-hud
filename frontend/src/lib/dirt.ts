// Shared by the tape, which composites it into what a widget drew, and by the
// glass slab, which lays it on the pane itself. One picture of dirt, so the
// glass and the tape never disagree about what dirty looks like.
//
// The dirt, as a picture of wear rather than as noise. Three kinds of it,
// stacked into one image:
//
// **Smudges.** Coarse turbulence with its low end thrown away: `feFuncA` is
// flat at zero for the first three fifths of the range and only climbs after
// that, so the bottom of the noise becomes clean glass and only the peaks
// survive as patches. On its own this read as "voronoi" — blobs and nothing
// finer — so since #214 it runs at 1.4x the frequency the 256px tile had, with
// a fourth octave for detail inside the patches.
//
// **Dust.** The same trick at five times the frequency and a harsher cut:
// only the top of a fine noise survives, as specks a pixel or two across. At
// the near-per-pixel frequency tried first, nothing reached the cut at all.
//
// **Scratches.** Hairlines from a seeded random generator, so the same
// scratches come back on every load. Most run along two wipe directions, the
// way a cloth leaves them, and the rest point anywhere. They are drawn nine
// times, once per neighbouring tile, so one that crosses an edge carries on
// into the next tile instead of stopping at a seam.
//
// The colour is one warm grey throughout and the alpha carries all the shape.
//
// It is an image and not primitives in the board's filter for the reason the
// grain before it was: `feTurbulence` inside the board's filter is generated
// per widget over that widget's whole region, and cost about a core and a half.
// This is rasterised once, cached, and only ever tiled — which is also why it
// can afford the detail. The tile is large, several widgets wide, so that each
// pane can start somewhere else in it (`dirtOffset`) and no two wear the same
// marks in the same corner.

/** The tile's side, in CSS pixels. */
export const DIRT_SIZE = 1024;

/** The warm grey every layer is painted in. */
const INK = "rgb(219,214,204)";

/** A small seeded generator (mulberry32): the same numbers on every load. */
function seeded(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Two decimals: enough for a hairline, and it keeps the image small. */
const at = (n: number): string => n.toFixed(2);

/** One hairline: a short, very slightly bent stroke. */
function scratch(random: () => number, angle: number, long: boolean): string {
  const length = long ? 180 + random() * 260 : 12 + random() * 110;
  const x = random() * DIRT_SIZE;
  const y = random() * DIRT_SIZE;
  const dx = Math.cos(angle) * length;
  const dy = Math.sin(angle) * length;
  // The bend, square to the stroke and a few percent of its length.
  const bend = (random() - 0.5) * 0.16 * length;
  const cx = x + dx / 2 - Math.sin(angle) * bend;
  const cy = y + dy / 2 + Math.cos(angle) * bend;
  const width = long ? 0.5 + random() * 0.3 : 0.5 + random() * 0.7;
  const alpha = long ? 0.12 + random() * 0.15 : 0.25 + random() * 0.45;
  return (
    `<path d='M${at(x)} ${at(y)}Q${at(cx)} ${at(cy)} ${at(x + dx)} ${at(y + dy)}'` +
    ` stroke-width='${at(width)}' stroke-opacity='${at(alpha)}'/>`
  );
}

/** Every scratch on the tile, as one group of paths. */
function scratches(): string {
  const random = seeded(214);
  // The two directions a cloth went, in radians, and how far a stroke strays.
  const wipes = [-0.35, 0.6];
  const stray = 0.14;
  const paths: string[] = [];
  for (let n = 0; n < 110; n += 1) {
    const wiped = random() < 0.7;
    const angle = wiped
      ? wipes[n % wipes.length] + (random() - 0.5) * 2 * stray
      : random() * Math.PI;
    paths.push(scratch(random, angle, n % 12 === 0));
  }
  return paths.join("");
}

/** A turbulence filter thresholded by `table`, painted in the ink. */
function noise(
  id: string,
  frequency: number,
  octaves: number,
  seed: number,
  table: string,
): string {
  return (
    `<filter id='${id}' x='0' y='0' width='${DIRT_SIZE}' height='${DIRT_SIZE}'` +
    ` filterUnits='userSpaceOnUse' color-interpolation-filters='sRGB'>` +
    `<feTurbulence type='fractalNoise' baseFrequency='${frequency}'` +
    ` numOctaves='${octaves}' seed='${seed}' stitchTiles='stitch'/>` +
    `<feColorMatrix type='matrix'` +
    ` values='0 0 0 0 0.86 0 0 0 0 0.84 0 0 0 0 0.8 1 0 0 0 0'/>` +
    `<feComponentTransfer><feFuncA type='table' tableValues='${table}'/>` +
    `</feComponentTransfer></filter>`
  );
}

/** The eight other places a scratch is drawn: the tiles around this one. */
function wrapped(): string {
  const copies: string[] = [];
  for (const x of [-DIRT_SIZE, 0, DIRT_SIZE]) {
    for (const y of [-DIRT_SIZE, 0, DIRT_SIZE]) {
      if (x !== 0 || y !== 0) {
        copies.push(`<use href='#s' x='${x}' y='${y}'/>`);
      }
    }
  }
  return copies.join("");
}

function picture(): string {
  const size = `width='${DIRT_SIZE}' height='${DIRT_SIZE}'`;
  return (
    `<svg xmlns='http://www.w3.org/2000/svg' ${size}>` +
    `<defs>` +
    noise("smudge", 0.07, 4, 7, "0 0 0 0 0.35 1") +
    noise("dust", 0.35, 2, 3, "0 0 0 0 0 0 0 0.6 1") +
    `</defs>` +
    `<rect ${size} filter='url(#smudge)'/>` +
    `<rect ${size} filter='url(#dust)'/>` +
    `<g id='s' fill='none' stroke='${INK}' stroke-linecap='round'>` +
    `${scratches()}</g>` +
    wrapped() +
    `</svg>`
  );
}

export const DIRT = `data:image/svg+xml,${encodeURIComponent(picture())}`;

/**
 * Where in the tile a widget's pane starts, from the widget's id.
 *
 * From the id rather than from a random number so it stays put: a pane that
 * picked a new patch of dirt on every render would shimmer, and one that picked
 * a new patch on every reload would not be the same pane. FNV-1a, because any
 * hash that spreads its output will do and this one is four lines.
 */
export function dirtOffset(id: string): { x: number; y: number } {
  let hash = 0x811c9dc5;
  for (let i = 0; i < id.length; i += 1) {
    hash = Math.imul(hash ^ id.charCodeAt(i), 0x01000193) >>> 0;
  }
  return { x: hash % DIRT_SIZE, y: (hash >>> 10) % DIRT_SIZE };
}
