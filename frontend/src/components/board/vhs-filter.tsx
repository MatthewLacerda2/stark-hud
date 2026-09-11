import type { Tape } from "@/lib/vhs";

// Four pixels of tube, one and a half of them dark. A filter has no primitive
// that makes stripes, so they arrive as an image and are tiled across whatever
// the filter is applied to.
const STRIPES =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='4' height='4'%3E%3Crect width='4' height='1.5' fill='%23000'/%3E%3C/svg%3E";

// The dirt, as a picture of dirt rather than as noise.
//
// Two things are going on inside this image, and they are the whole difference
// between dirt and grain.
//
// The turbulence is *coarse* — about thirteen cells across the tile, three
// octaves — so it varies over tens of pixels rather than per pixel. That gives
// patches. Then `feFuncA` throws the low end away: the table is flat at zero
// for the first three fifths of the range and only climbs after that, so the
// bottom of the noise becomes clean glass and only the peaks survive. Measured
// on the rasterised tile, 87% of it is below 0.05 alpha and a surviving pixel
// has 3.45 of its 4 neighbours surviving too, where scattering the same pixels
// at random would give 0.53. Most of the surface is clean and what is left
// collects in clumps of roughly five to twenty-five pixels across.
//
// The colour is a constant warm grey and the alpha carries all the shape, which
// is what the colour matrix does: RGB from the last column, alpha tapped off
// the red channel of the turbulence.
//
// It is an image and not primitives in the filter below for the reason the
// grain before it was: `feTurbulence` inside the board's filter is generated
// per widget over that widget's whole region, and cost about a core and a half.
// Here it is run once, inside a 256px image the browser rasterises and caches,
// and the filter only tiles it. A tile that size is about one widget wide on
// this board, so the repeat usually falls outside the widget showing it.
const DIRT =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='256' height='256'%3E%3Cfilter id='d' x='0' y='0' width='256' height='256' filterUnits='userSpaceOnUse' color-interpolation-filters='sRGB'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.05' numOctaves='3' seed='7' stitchTiles='stitch'/%3E%3CfeColorMatrix type='matrix' values='0 0 0 0 0.86 0 0 0 0 0.84 0 0 0 0 0.8 1 0 0 0 0'/%3E%3CfeComponentTransfer%3E%3CfeFuncA type='table' tableValues='0 0 0 0 0.35 1'/%3E%3C/feComponentTransfer%3E%3C/filter%3E%3Crect width='256' height='256' filter='url(%23d)'/%3E%3C/svg%3E";

/**
 * Dirt on the glass in front of the readout, and the lines of the tube through
 * it.
 *
 * Both composite into `SourceAlpha`, which is the shape of what the widget
 * actually painted. A layer over the widget's rectangle would put the dirt on
 * the room showing through a transparent widget instead of on the board, which
 * is why the layers this replaced were removed in the first place.
 *
 * That choice is also what makes the dirt land where dirt shows. `SourceAlpha`
 * is mostly thin bright strokes — letters, rings, icons — and a light smear
 * over a thin bright stroke is imperceptible; the one place a widget has real
 * area is its panel. So the dirt appears on the panel and nowhere else worth
 * seeing, without anything here being told about the panel. And because a panel
 * at a third is a third of the way present in `SourceAlpha`, the dirt over it
 * is a third as strong, and a widget with no panel has no glass to be dirty.
 *
 * Nothing here moves. The grain used to drift five times a second, and every
 * step of it was a repaint of every filtered widget — the single most expensive
 * thing on this board. A television is looked at from a sofa, not stared into,
 * and motion in a texture reads as a fault in the screen rather than as a look.
 *
 * Rendered once for the whole board. A filter is a definition, and ten widgets
 * pointing at one is ten widgets and one definition.
 */
export function VhsFilter({ tape }: { tape: Tape }) {
  if (tape.grain <= 0 && tape.scanlines <= 0) return null;
  // The ceilings, again — the amount of each that is a texture rather than a
  // fault. They are the filter's own because alpha inside a filter and opacity
  // on a layer are not the same quantity.
  //
  // The dirt's is higher than the grain's 0.16 was and means much less ink: the
  // grain covered every pixel it touched, the dirt covers about an eighth of
  // them. Over the whole surface that is 0.012 of ink against the grain's
  // 0.080, while inside a clump it is 0.081 and peaks at 0.30 — fainter
  // overall, and stronger where it actually is, which is what a patch is.
  const dirt = tape.grain * 0.55;
  const scanlines = tape.scanlines * 0.24;

  return (
    <svg aria-hidden className="pointer-events-none absolute size-0">
      <defs>
        <filter id="vhs-tape" colorInterpolationFilters="sRGB">
          <feImage href={DIRT} width="256" height="256" result="dust" />
          <feTile in="dust" result="spread" />
          <feComponentTransfer in="spread" result="dimDust">
            <feFuncA type="linear" slope={dirt} />
          </feComponentTransfer>
          {/* The whole point: keep the texture only where the widget drew. */}
          <feComposite
            in="dimDust"
            in2="SourceAlpha"
            operator="in"
            result="dirt"
          />
          {/* Overlay, so a smear lifts the dark panel it sits on the way dirt
              catches light against a black screen, rather than covering it. */}
          <feBlend
            in="dirt"
            in2="SourceGraphic"
            mode="overlay"
            result="dirtied"
          />

          <feImage
            href={STRIPES}
            x="0"
            y="0"
            width="4"
            height="4"
            result="stripe"
          />
          <feTile in="stripe" result="tiled" />
          <feComponentTransfer in="tiled" result="dimmed">
            <feFuncA type="linear" slope={scanlines} />
          </feComponentTransfer>
          <feComposite
            in="dimmed"
            in2="SourceAlpha"
            operator="in"
            result="lines"
          />
          {/* Multiply, so a line is the tube leaving less of what was there
              rather than a grey bar laid on top of it. */}
          <feBlend in="lines" in2="dirtied" mode="multiply" />
        </filter>
      </defs>
    </svg>
  );
}
