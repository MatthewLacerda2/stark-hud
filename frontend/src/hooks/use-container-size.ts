import { useEffect, useRef, useState } from "react";

/**
 * Measure an element's box.
 *
 * The board draws itself in percentages and needs no measurement to be correct.
 * This is for the one thing that does: turning a pointer's travel in pixels into
 * columns and rows, which is how far a drag has actually moved a widget.
 */
export function useContainerSize(): {
  ref: React.RefObject<HTMLDivElement | null>;
  width: number;
  height: number;
} {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize((current) =>
        current.width === width && current.height === height
          ? current
          : { width, height },
      );
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return { ref, width: size.width, height: size.height };
}
