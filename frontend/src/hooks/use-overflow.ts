import { useEffect, useRef, useState } from "react";

/**
 * How far a block overflows its box, in pixels, or 0 when it fits.
 *
 * Re-measured whenever the element or its content resizes, because a tile can
 * be dragged to a new size at any moment and text that fitted may stop fitting.
 */
export function useOverflow(deps: unknown): {
  ref: React.RefObject<HTMLDivElement | null>;
  overflow: number;
} {
  const ref = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState(0);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const measure = () => {
      const amount = Math.max(0, element.scrollHeight - element.clientHeight);
      setOverflow((current) => (current === amount ? current : amount));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    if (element.firstElementChild) observer.observe(element.firstElementChild);
    return () => observer.disconnect();
  }, [deps]);

  return { ref, overflow };
}
