import type { Tape } from "@/lib/vhs";

/** One layer of the look. Absent, not transparent, when it is turned off. */
function Layer({ className, amount }: { className: string; amount: number }) {
  if (amount <= 0) return null;
  return <div className={className} />;
}

/**
 * The two parts of the tape that belong to the panel rather than to what is
 * written on it.
 *
 * Grain and scanlines are not here any more. They fall on what the widget drew,
 * which a rectangle cannot express, so they moved into a filter — see
 * `vhs-filter.tsx`. What is left is a vignette and the tracking bar, and both
 * of those are things that happen to a panel: they exist to the extent the
 * panel does, which is what the multiplication by `--widget-alpha` says. Turn a
 * widget's background off and these go with it, because there is nothing left
 * for them to happen to and the video behind is not theirs to touch.
 *
 * The clip keeps the bar inside the pane on its way past. It is deliberately
 * not given a `z-index`, so it does not become a stacking context of its own.
 */
export function Vhs({ tape }: { tape: Tape }) {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-xl">
      <Layer className="vhs-sweep" amount={tape.sweep} />
      <Layer className="vhs-vignette" amount={tape.vignette} />
    </div>
  );
}
