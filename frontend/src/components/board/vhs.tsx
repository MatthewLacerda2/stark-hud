import type { Tape } from "@/lib/vhs";

/** One layer of the look. Absent, not transparent, when it is turned off. */
function Layer({ className, amount }: { className: string; amount: number }) {
  if (amount <= 0) return null;
  return <div className={className} />;
}

/**
 * The tape look, drawn over one widget.
 *
 * Over a widget rather than over the board, because the board is a window onto
 * a room and the widgets are the panes held up in front of it. Grain and
 * scanlines over the whole screen said the television was old; the same grain
 * stopping at the edge of each pane says the *panel* is a display and the room
 * behind it is simply the room.
 *
 * Four layers, each a flat colour or a gradient moved with a transform —
 * nothing here reads the pixels underneath. A filter that did would re-run over
 * moving video every frame on a machine already spending a core decoding it.
 *
 * The clip is what keeps the grain inside the pane: it is twice the size of
 * what it covers so there is always tile to move into. It is deliberately not
 * given a `z-index`, so it does not become a stacking context of its own and
 * the grain still has the widget under it to blend with. It also carries how
 * much pane there is — see `vhs-pane` — so a widget turned down to nothing
 * takes its tape with it and leaves the video underneath alone.
 *
 * The fifth part, the colour fringe on the letters, is not here: it is a
 * text-shadow, which is inherited, so it is a class on the board.
 */
export function Vhs({ tape }: { tape: Tape }) {
  return (
    <div className="vhs-pane pointer-events-none absolute inset-0 overflow-hidden rounded-xl">
      <Layer className="vhs-scanlines" amount={tape.scanlines} />
      <Layer className="vhs-grain" amount={tape.grain} />
      <Layer className="vhs-sweep" amount={tape.sweep} />
      <Layer className="vhs-vignette" amount={tape.vignette} />
    </div>
  );
}
