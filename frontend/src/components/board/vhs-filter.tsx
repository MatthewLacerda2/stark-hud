import type { Tape } from "@/lib/vhs";

// Four pixels of tube, one and a half of them dark. A filter has no primitive
// that makes stripes, so they arrive as an image and are tiled across whatever
// the filter is applied to.
const STRIPES =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='4' height='4'%3E%3Crect width='4' height='1.5' fill='%23000'/%3E%3C/svg%3E";

// The grain, as a picture of noise rather than as noise.
//
// `feTurbulence` in the filter itself cost about a core and a half across the
// board: it is generated per widget, over that widget's whole region, and back
// when the grain drifted it did that several times a second. Here the
// turbulence is run once, inside a 220px image the browser rasterises and
// caches, and the filter only tiles it. Same grain, computed once for the
// session.
const NOISE =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='220' height='220'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='matrix' values='0.33 0.33 0.33 0 0 0.33 0.33 0.33 0 0 0.33 0.33 0.33 0 0 0 0 0 0 1'/%3E%3C/filter%3E%3Crect width='220' height='220' filter='url(%23n)'/%3E%3C/svg%3E";

/**
 * The tape, as something that happens to what a widget drew.
 *
 * The layers this replaces were drawn over the widget's rectangle, which meant
 * grain and scanlines fell on the empty parts of a transparent widget — on the
 * room behind the board rather than on the board. A filter does not have that
 * problem: `SourceAlpha` is the shape of what the widget actually painted, and
 * compositing the texture *into* it puts the tape on the letters, the rings,
 * the icons and the panel, and nowhere else.
 *
 * That is also why nothing here has to be told about the opacity slider. A
 * panel at a third is a third of the way present in `SourceAlpha`, so the tape
 * over it is a third as strong, and a panel turned off contributes nothing —
 * while the text on top of it, which is not the panel, keeps the tape at full.
 *
 * Nothing here moves. The grain used to drift five times a second, and every
 * step of it was a repaint of every filtered widget — the single most expensive
 * thing on this board. Still grain, still a tube; it simply sits there now, so
 * the browser rasterises each widget once and keeps it. A television is looked
 * at from a sofa, not stared into, and motion in the texture reads as a fault
 * in the screen rather than as a look.
 *
 * Rendered once for the whole board. A filter is a definition, and ten widgets
 * pointing at one is ten widgets and one definition.
 */
export function VhsFilter({ tape }: { tape: Tape }) {
  if (tape.grain <= 0 && tape.scanlines <= 0) return null;
  // The ceilings, again — the amount of each that is a texture rather than a
  // fault. They are the filter's own because alpha inside a filter and opacity
  // on a layer are not the same quantity.
  const grain = tape.grain * 0.16;
  const scanlines = tape.scanlines * 0.24;

  return (
    <svg aria-hidden className="pointer-events-none absolute size-0">
      <defs>
        <filter id="vhs-tape" colorInterpolationFilters="sRGB">
          <feImage href={NOISE} width="220" height="220" result="noise" />
          <feTile in="noise" result="grainy" />
          <feComponentTransfer in="grainy" result="dimGrain">
            <feFuncA type="linear" slope={grain} />
          </feComponentTransfer>
          {/* The whole point: keep the texture only where the widget drew. */}
          <feComposite
            in="dimGrain"
            in2="SourceAlpha"
            operator="in"
            result="grain"
          />
          <feBlend
            in="grain"
            in2="SourceGraphic"
            mode="overlay"
            result="grained"
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
          <feBlend in="lines" in2="grained" mode="multiply" />
        </filter>
      </defs>
    </svg>
  );
}
