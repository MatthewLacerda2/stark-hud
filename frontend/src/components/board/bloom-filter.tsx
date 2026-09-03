/**
 * The glow, as something that happens to what a widget drew.
 *
 * Three steps, which is all bloom has ever been: keep the parts that are
 * bright, blur them, and add the blur back on top. Adding rather than covering
 * is the whole trick — light falls on what is already there instead of hiding
 * it, so a lit letter keeps its shape and gains a halo.
 *
 * `SourceAlpha` never appears here, unlike the tape, and that is deliberate.
 * The tape is a texture that must land only on what the widget painted; bloom
 * is light, and light leaves. The blur carries the widget's own alpha outward
 * past its edges, which is why the filter region below is wider than the
 * widget: clipped at the boundary the glow would stop dead in a straight line,
 * and a straight edge is the one thing light never has.
 *
 * Rendered once for the whole board. Ten widgets pointing at one definition is
 * ten widgets and one definition.
 */
import { lit, type Bloom } from "@/lib/bloom";

/** The widest the light carries, in pixels, at `spread` of one. */
const REACH = 12;

/**
 * Quality, which is fixed rather than a dial.
 *
 * One blur is a halo; light is not a halo. What a lit thing actually does is
 * put a tight bright core right against its edge and a broad faint wash a long
 * way past it, and no single gaussian has both — narrow loses the wash, wide
 * loses the core. So the highlights are blurred three times at widening radii
 * and summed, which is the same trick a game plays with a mip chain, and the
 * falloff stops reading as blur and starts reading as light.
 *
 * Three and not more: each one is another pass over every lit widget, and the
 * fourth is not visible from a sofa. The weights sum to one so that turning
 * quality up never quietly turned brightness up with it.
 */
const OCTAVES = [
  { scale: 1, weight: 0.5 },
  { scale: 2, weight: 0.3 },
  { scale: 3.5, weight: 0.2 },
];

export function BloomFilter({ bloom }: { bloom: Bloom }) {
  if (!lit(bloom)) return null;

  // Everything at or below the cutoff lands on or under zero and is clamped
  // away; 1 stays 1. So the pass keeps the highlights and their shape, rather
  // than dimming the whole picture and blurring that. A cutoff of 1 would
  // divide by nothing, so it stops just short of the top.
  const cutoff = Math.min(bloom.cutoff, 0.99);
  const slope = 1 / (1 - cutoff);
  const intercept = -cutoff * slope;
  const spread = bloom.spread * REACH;

  return (
    <svg aria-hidden className="pointer-events-none absolute size-0">
      <defs>
        <filter
          id="bloom"
          // Light adds in linear space, not in the space a screen displays.
          // Summing these in sRGB gives a halo that goes muddy in the middle
          // of its falloff — the arithmetic is being done on numbers that were
          // bent for a display rather than on quantities of light. This is the
          // single biggest difference between a glow that reads as lit and one
          // that reads as a blurred copy, and it is why the tape next door
          // chooses the opposite: a texture wants the display's space.
          colorInterpolationFilters="linearRGB"
          x="-25%"
          y="-25%"
          width="150%"
          height="150%"
        >
          <feComponentTransfer in="SourceGraphic" result="bright">
            <feFuncR type="linear" slope={slope} intercept={intercept} />
            <feFuncG type="linear" slope={slope} intercept={intercept} />
            <feFuncB type="linear" slope={slope} intercept={intercept} />
          </feComponentTransfer>

          {OCTAVES.map((octave, i) => (
            <feGaussianBlur
              key={octave.scale}
              in="bright"
              stdDeviation={spread * octave.scale}
              result={`octave${i}`}
            />
          ))}

          {/* Summed one onto the next, each carrying its own weight. The first
              pair is weighted on both sides; after that the running total is
              already weighted and only the newcomer needs scaling. */}
          <feComposite
            in="octave0"
            in2="octave1"
            operator="arithmetic"
            k2={OCTAVES[0].weight}
            k3={OCTAVES[1].weight}
            result="sum1"
          />
          <feComposite
            in="sum1"
            in2="octave2"
            operator="arithmetic"
            k2={1}
            k3={OCTAVES[2].weight}
            result="glow"
          />

          {/* k2 is how much light, k3 keeps the widget itself whole underneath.
              Arithmetic rather than a blend mode because light adds, and the
              blend modes that look like adding all cap somewhere. */}
          <feComposite
            in="glow"
            in2="SourceGraphic"
            operator="arithmetic"
            k2={bloom.glow}
            k3={1}
          />
        </filter>
      </defs>
    </svg>
  );
}
