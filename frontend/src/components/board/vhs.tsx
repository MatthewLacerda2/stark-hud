import type { Tape } from "@/lib/vhs";

/** One layer of the look. Absent, not transparent, when it is turned off. */
function Layer({ className, amount }: { className: string; amount: number }) {
  if (amount <= 0) return null;
  return <div className={className} />;
}

/**
 * The tape look, drawn over the finished board.
 *
 * Four layers, each of which is a flat colour or a gradient moved about with a
 * transform — nothing here reads the pixels underneath, because a filter that
 * did would have to re-run over a 1920x1080 video thirty times a second on a
 * machine that is already spending a core decoding it.
 *
 * They are siblings rather than children of a wrapper on purpose. The grain
 * blends with what is behind it, and an element that blends only does so within
 * the nearest stacking context — put these inside a positioned wrapper of their
 * own and the grain would have nothing to mix with but itself.
 *
 * The fifth part, the colour fringe on text, is not here: it is a text-shadow,
 * which is inherited, so it is a class on the board rather than a layer over it.
 */
export function Vhs({ tape }: { tape: Tape }) {
  return (
    <>
      <Layer className="vhs-scanlines" amount={tape.scanlines} />
      <Layer className="vhs-grain" amount={tape.grain} />
      <Layer className="vhs-sweep" amount={tape.sweep} />
      <Layer className="vhs-vignette" amount={tape.vignette} />
    </>
  );
}
