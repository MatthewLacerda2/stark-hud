import { useEffect, useRef, useState } from "react";

/**
 * How many children fit in a box without being cut in half.
 *
 * Nobody can scroll this screen, so a list longer than its widget has to lose
 * the tail — and `overflow: hidden` on its own loses it mid-row, which on a
 * television reads as a fault rather than as a boundary. This counts the rows
 * that fit whole, so the caller can hide the one straddling the edge.
 *
 * Hide them with `visibility`, never `display`: a row taken out of the layout
 * would free the space that decided it did not fit, and the measurement would
 * oscillate. Left in the layout, hiding a row moves nothing above it, so one
 * pass settles.
 */
/** One row's place in the box, in pixels: where it starts and how tall it is. */
export interface Row {
  top: number;
  height: number;
}

/**
 * How many of these rows fit whole in a box that tall.
 *
 * Split out from the measuring because this is the part that can be wrong, and
 * the measuring is the part that needs a browser. A pixel of tolerance, so
 * sub-pixel layout does not cost a whole row.
 */
export function fitting(rows: Row[], room: number): number {
  const past = rows.findIndex((row) => row.top + row.height > room + 1);
  return past === -1 ? rows.length : past;
}

export function useFitting(deps: unknown): {
  ref: React.RefObject<HTMLUListElement | null>;
  fits: number;
} {
  const ref = useRef<HTMLUListElement>(null);
  // Everything, until something has been measured. One frame of a clipped row
  // is better than a frame with nothing in it.
  const [fits, setFits] = useState(Number.POSITIVE_INFINITY);

  useEffect(() => {
    const box = ref.current;
    if (!box) return;
    const measure = () => {
      const rows = [...box.children].map((child) => ({
        top: (child as HTMLElement).offsetTop,
        height: (child as HTMLElement).offsetHeight,
      }));
      const count = fitting(rows, box.clientHeight);
      setFits((current) => (current === count ? current : count));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(box);
    for (const child of box.children) observer.observe(child);
    return () => observer.disconnect();
  }, [deps]);

  return { ref, fits };
}
