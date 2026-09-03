import { useEffect, useState } from "react";

const HALF_MINUTE_MS = 30_000;

/**
 * Re-render on a slow tick, so anything showing a time stops being a lie.
 *
 * A component that prints "now" prints it once and keeps printing it: nothing
 * about the board changed, so nothing re-rendered, and the label outlived the
 * minute it was true in.
 *
 * Half a minute is right for anything showing a clock time. A countdown asks
 * for a second in its last minute, and for nothing faster the rest of the time:
 * seconds are noise on a screen nobody is standing at until they are the only
 * thing left to say.
 *
 * It hands back the moment it last ticked to, so a component can work out what
 * to draw without reading a clock in its own render — which is impure, and
 * which the compiler is right to complain about.
 */
export function useClock(everyMs: number = HALF_MINUTE_MS): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(timer);
  }, [everyMs]);
  return now;
}
