import { useEffect, type RefObject } from "react";
import {
  lean,
  leanShift,
  moving,
  recede,
  type Depth,
  type Pointer,
} from "@/lib/depth";

/**
 * How long the board takes to catch up with the pointer, in seconds.
 *
 * A board that tracks the pointer exactly is a board stuck to it. A quarter of a
 * second is enough for the lean to feel like weight being pushed rather than a
 * picture following the mouse.
 */
const FOLLOW_SECONDS = 0.25;

/** Close enough to where the pointer is that another frame would change nothing. */
const SETTLED = 0.001;

const STILL: Depth = { tilt: 0, sway: 0, glass: 0 };

/**
 * Lean the board: away from the pointer, and slowly on its own.
 *
 * Written straight onto the element's style every frame rather than through
 * React state. The lean is one transform on one element, and routing it through
 * a render would re-render every widget on the board sixty times a second to
 * change a number none of them read.
 *
 * The loop stops when there is nothing to do: no sway, and the board already
 * where the pointer put it. That is the whole life of this hook on a television,
 * which has no pointer — unless sway is on, which is the one part that is meant
 * to run with nobody there.
 *
 * `still` levels the board, for a widget that has the whole screen: a film does
 * not lean.
 */
export function useLean(
  ref: RefObject<HTMLElement | null>,
  depth: Depth,
  still: boolean,
) {
  useEffect(() => {
    const element = ref.current;
    if (!element || !moving(depth)) return;
    const asked = still ? STILL : depth;

    const target: Pointer = { x: 0, y: 0 };
    const at: Pointer = { x: 0, y: 0 };
    const started = performance.now();
    let last = started;
    let frame = 0;

    const draw = (now: number) => {
      // Capped, so a tab that was hidden for a minute catches up in one smooth
      // step rather than snapping.
      const step = Math.min((now - last) / 1000, 0.1);
      last = now;
      const follow = 1 - Math.exp(-step / FOLLOW_SECONDS);
      at.x += (target.x - at.x) * follow;
      at.y += (target.y - at.y) * follow;

      const turned = lean(asked, at, (now - started) / 1000);
      const back = recede(turned, element.clientWidth, element.clientHeight);
      element.style.transform = `translateZ(${-back}px) rotateX(${turned.x}deg) rotateY(${turned.y}deg)`;
      // For what is drawn behind a widget's face without being in the 3D scene:
      // the extruded icons and chart marks. See `leanShift`.
      const shift = leanShift(turned);
      element.style.setProperty("--lean-x", String(shift.x));
      element.style.setProperty("--lean-y", String(shift.y));

      const settled =
        Math.abs(target.x - at.x) < SETTLED &&
        Math.abs(target.y - at.y) < SETTLED;
      frame = asked.sway > 0 || !settled ? requestAnimationFrame(draw) : 0;
    };

    const wake = () => {
      if (frame) return;
      last = performance.now();
      frame = requestAnimationFrame(draw);
    };
    const point = (event: PointerEvent) => {
      target.x = (event.clientX / window.innerWidth) * 2 - 1;
      target.y = (event.clientY / window.innerHeight) * 2 - 1;
      wake();
    };
    // Out of the window altogether, which is the only `pointerout` with nothing
    // on the other side of it. The board comes back to rest.
    const leave = (event: PointerEvent) => {
      if (event.relatedTarget !== null) return;
      target.x = 0;
      target.y = 0;
      wake();
    };

    window.addEventListener("pointermove", point);
    document.addEventListener("pointerout", leave);
    wake();
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", point);
      document.removeEventListener("pointerout", leave);
      element.style.transform = "";
      element.style.removeProperty("--lean-x");
      element.style.removeProperty("--lean-y");
    };
  }, [ref, depth, still]);
}
