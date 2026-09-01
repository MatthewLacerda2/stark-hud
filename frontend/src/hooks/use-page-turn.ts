import { useEffect } from "react";

// A trackpad swipe arrives as a stream of small deltas, so one gesture would
// otherwise turn several pages. This is roughly one flick.
const SWIPE_PX = 120;
const SWIPE_QUIET_MS = 500;

/**
 * Turning the page sideways: arrow keys, or a horizontal swipe.
 *
 * Both are for whoever is at a laptop. The TV has neither, which is the whole
 * reason the page lives on the server: turning it here turns it there.
 */
export function usePageTurn(turn: (delta: number) => void) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight") turn(1);
      else if (event.key === "ArrowLeft") turn(-1);
    };

    let travelled = 0;
    let settle: ReturnType<typeof setTimeout> | undefined;

    const onWheel = (event: WheelEvent) => {
      // Vertical scrolling is not ours: the board does not scroll, and a
      // two-finger scroll down should not sidestep into the next page.
      if (Math.abs(event.deltaX) <= Math.abs(event.deltaY)) return;
      travelled += event.deltaX;
      clearTimeout(settle);
      settle = setTimeout(() => (travelled = 0), SWIPE_QUIET_MS);
      if (Math.abs(travelled) >= SWIPE_PX) {
        turn(travelled > 0 ? 1 : -1);
        travelled = 0;
      }
    };

    window.addEventListener("keydown", onKey);
    window.addEventListener("wheel", onWheel, { passive: true });
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("wheel", onWheel);
      clearTimeout(settle);
      if (settle) clearTimeout(settle);
    };
  }, [turn]);
}
