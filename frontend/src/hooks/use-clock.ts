import { useEffect, useState } from "react";

const HALF_MINUTE_MS = 30_000;

/**
 * Re-render on a slow tick, so anything showing a time stops being a lie.
 *
 * A component that prints "now" prints it once and keeps printing it: nothing
 * about the board changed, so nothing re-rendered, and the label outlived the
 * minute it was true in.
 */
export function useClock(): void {
  const [, tick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => tick((n) => n + 1), HALF_MINUTE_MS);
    return () => clearInterval(timer);
  }, []);
}
