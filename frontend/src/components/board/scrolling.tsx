import type { ReactNode } from "react";
import { useOverflow } from "@/hooks/use-overflow";

// Constant speed rather than constant duration: a long list should not race.
const PIXELS_PER_SECOND = 18;
const MIN_SECONDS = 8;

/**
 * A box that scrolls itself when what is in it does not fit, and sits still
 * when it does.
 *
 * Nobody can scroll this screen, so anything that overflows would simply be
 * lost. It also gives the board something moving when nothing is happening,
 * which is half the point of having it on a wall.
 *
 * It takes children rather than a string because a list may hold rows now, and
 * a row is not text: the measuring and the animation never cared what was
 * inside, only how tall it turned out to be.
 */
export function Scrolling({
  children,
  /** What to re-measure on when it changes: the content, in whatever form. */
  content,
  className = "",
  color,
}: {
  children: ReactNode;
  content: unknown;
  className?: string;
  /** Overrides the inherited colour. The inner element owns `style` already. */
  color?: string;
}) {
  const { ref, overflow } = useOverflow(content);
  const seconds = Math.max(MIN_SECONDS, (overflow / PIXELS_PER_SECOND) * 2);

  return (
    <div
      ref={ref}
      className={`min-h-0 overflow-hidden ${className}`}
      style={color ? { color } : undefined}
    >
      <div
        style={
          overflow > 0
            ? {
                animation: `node-scroll ${seconds}s ease-in-out infinite`,
                ["--scroll-distance" as string]: `${overflow}px`,
              }
            : undefined
        }
      >
        {children}
      </div>
    </div>
  );
}
