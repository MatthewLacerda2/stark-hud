import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * A widget acknowledging that work is coming, before any of it arrives.
 *
 * The interface moves first and the content lands a beat later: somebody said
 * they were about to write here, and the widget's own edge comes up and
 * breathes while they go and work out what to write. Everything that writes to
 * this board returns in milliseconds, so the wait a room actually sits through
 * is the thinking between two calls — which is the only thing this is for.
 *
 * Three states and two timers, because it has to end on its own in both of the
 * ways it can end. The answer arriving releases it; nothing arriving at all
 * releases it too, a little later, so a session that dies mid-thought does not
 * leave a widget lit until morning.
 */

/**
 * How long it holds before giving up by itself. Past Nielsen's ten seconds the
 * acknowledgement has said everything it can say, and going on saying it is how
 * a HUD turns into a spinner.
 */
const HOLD_MS = 11_000;

/**
 * The release. Long enough to read as the stroke dissolving rather than being
 * switched off, and over before an eye that moved to the new content is back.
 * Must match the transition in `widget-wake`.
 */
const SETTLE_MS = 520;

type Phase = "off" | "awake" | "settling";

export function WidgetWake({ nonce }: { nonce: number }) {
  const [phase, setPhase] = useState<Phase>("off");
  const [told, setTold] = useState(0);

  // The count goes up each time the server says work is coming and back to zero
  // when the write lands. Arrival is a release, never a switch-off: the stroke
  // fades out over the content appearing, so the two are one movement.
  //
  // Adjusted during the render rather than in an effect, which is React's own
  // answer to state that has to follow a prop: nothing is painted awake and
  // then immediately repainted.
  if (nonce !== told) {
    setTold(nonce);
    setPhase(nonce > 0 ? "awake" : phase === "awake" ? "settling" : phase);
  }

  // `told` is a dependency so that waking an already-awake widget restarts the
  // hold. Without it the second wake would end on the first one's timer, and
  // long work would go dark halfway through.
  useEffect(() => {
    if (phase === "off") return;
    const timer = setTimeout(
      () => setPhase(phase === "awake" ? "settling" : "off"),
      phase === "awake" ? HOLD_MS : SETTLE_MS,
    );
    return () => clearTimeout(timer);
  }, [phase, told]);

  if (phase === "off") return null;
  return (
    <div
      aria-hidden
      data-wake={phase}
      className={cn("widget-wake", phase === "settling" && "widget-wake-out")}
    />
  );
}
