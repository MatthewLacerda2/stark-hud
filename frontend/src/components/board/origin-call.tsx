import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

/**
 * The call that made a widget, beside it, for about two seconds.
 *
 * What a terminal gives away for free: Claude Code prints the command it is
 * about to run, and watching that scroll past is most of what makes a session
 * feel alive. The board had none of it — things simply appeared — so from the
 * sofa it changed by itself, which is accurate and a little dead.
 *
 * **Texture, not a log.** Nobody reads a line of JSON going past in two seconds
 * from ten feet away, and nothing here is built as though they might. It is the
 * look of a machine being told what to do: small, dim, monospaced, over the
 * widgets and under everything that matters. Unreadable from the sofa is the
 * design and not a shortcoming — if this ever wants to be read it wants a
 * different design and its own argument.
 *
 * It ends itself, and the board is never told. There is nothing to clean up and
 * nothing to acknowledge: an origin that has finished playing draws nothing and
 * is pushed out of state by the next few calls, which is the whole of its life
 * cycle.
 */

/**
 * How long it is on screen. Must match `--motion-origin` in `styles.css`, and
 * `SECONDS` in `backend/services/origin.py`, where the same number is also the
 * window that caps how many of these run at once.
 *
 * A timer rather than the animation's own end, for the case the animation never
 * runs: asked for stillness this element is never drawn, and something that
 * waited for an `animationend` in that case would wait for ever.
 */
const ORIGIN_MS = 2000;

export function OriginCall({
  text,
  /** Where it sits, in the board's coordinate space. */
  style,
}: {
  text: string;
  style: CSSProperties;
}) {
  const [gone, setGone] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setGone(true), ORIGIN_MS);
    return () => clearTimeout(timer);
  }, []);

  if (gone) return null;
  return (
    <div
      aria-hidden
      className="origin-call pointer-events-none absolute overflow-hidden rounded-lg px-2 py-1"
      style={style}
    >
      <div className="origin-call-line font-mono text-node-sm break-all text-muted-foreground">
        {text}
      </div>
    </div>
  );
}
