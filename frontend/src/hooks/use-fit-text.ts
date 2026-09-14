import { useLayoutEffect, useRef, useState } from "react";

/**
 * Type that is as large as its box allows, and no larger than the house size.
 *
 * A flow's box is a fraction of the widget and its word is whatever was
 * dictated, so neither knows about the other: a long name in a thin box spills
 * out of it, and a short one in a tall box sits in the middle of nothing. The
 * fix is the same both ways — find the largest size at which the word fits,
 * up to the widget's own type size, so a diagram of short words is not a
 * ransom note and a diagram of long ones is not clipped.
 *
 * The search is split from the measuring, as in `use-fitting.ts`: the search
 * is the part that can be wrong, and the measuring needs a browser.
 */

/** Below this nobody on a sofa can read it, so there is no point going lower. */
const FLOOR = 6;

/**
 * The largest size, on a half-pixel grid, at which `fits` says yes.
 *
 * `fits` must be monotone — what fits at one size fits at every smaller one —
 * which text in a fixed box is. Answers `ceiling` outright when that fits, and
 * `floor` when nothing does, because the alternative to a clipped word is no
 * word. Each probe costs a layout, so this is a bisection and not a walk.
 */
export function largest(
  fits: (size: number) => boolean,
  ceiling: number,
  floor: number = FLOOR,
): number {
  // Half-pixel units, so the loop is over integers and ends where it should.
  let low = Math.ceil(floor * 2);
  let high = Math.floor(ceiling * 2);
  if (high <= low || fits(high / 2)) return Math.max(high, low) / 2;
  // From here `high` is known not to fit and `low` is taken to.
  while (high - low > 1) {
    const mid = (low + high) >> 1;
    if (fits(mid / 2)) low = mid;
    else high = mid;
  }
  return low / 2;
}

/**
 * The font size, in pixels, that fits `text` inside the element's parent.
 *
 * The element must fill its parent's width and be clipped at its height, so
 * that `scrollWidth` says when a word will not break and `scrollHeight` when
 * the lines will not stack. Its ceiling is whatever size its own classes give
 * it, read with the inline size cleared — so the token, and `--widget-scale`
 * with it, still decide the most a word may be.
 *
 * Re-measured when the parent resizes, not when the element does: the element
 * resizes every time this sets a size, and that way lies a loop.
 *
 * `undefined` until a browser has measured, so jsdom draws the token size.
 */
export function useFitText(text: string): {
  ref: React.RefObject<HTMLSpanElement | null>;
  size: number | undefined;
} {
  const ref = useRef<HTMLSpanElement>(null);
  const [size, setSize] = useState<number>();

  useLayoutEffect(() => {
    const element = ref.current;
    const box = element?.parentElement;
    if (!element || !box) return;
    const measure = () => {
      element.style.fontSize = "";
      const ceiling = Number.parseFloat(getComputedStyle(element).fontSize);
      if (!Number.isFinite(ceiling) || ceiling <= 0) return;
      const fits = (at: number) => {
        element.style.fontSize = `${at}px`;
        // A pixel of tolerance, as `fitting` gives: sub-pixel layout rounds
        // and a descender's pixel is not an overflow anybody can see.
        return (
          element.scrollHeight <= element.clientHeight + 1 &&
          element.scrollWidth <= element.clientWidth + 1
        );
      };
      const found = largest(fits, ceiling);
      element.style.fontSize = `${found}px`;
      setSize((current) => (current === found ? current : found));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(box);
    return () => observer.disconnect();
  }, [text]);

  return { ref, size };
}
