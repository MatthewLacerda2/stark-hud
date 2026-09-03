import type { Tape } from "@/lib/vhs";

/** One layer of the look. Absent, not transparent, when it is turned off. */
function Layer({ className, amount }: { className: string; amount: number }) {
  if (amount <= 0) return null;
  return <div className={className} />;
}

/**
 * The part of the tape that belongs to the panel rather than to what is written
 * on it.
 *
 * Grain and scanlines are not here any more. They fall on what the widget drew,
 * which a rectangle cannot express, so they moved into a filter — see
 * `vhs-filter.tsx`. What is left is the vignette, which is a thing that happens to a
 * panel: it exists to the extent the panel does, which is what the
 * multiplication by `--widget-alpha` says. Turn a
 * widget's background off and it goes with it, because there is nothing left
 * for it to happen to and the video behind is not its to touch.
 *
 * The clip is deliberately not given a `z-index`, so it does not become a
 * stacking context of its own.
 */
export function Vhs({ tape }: { tape: Tape }) {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-xl">
      <Layer className="vhs-vignette" amount={tape.vignette} />
    </div>
  );
}
