import { useOverflow } from "@/hooks/use-overflow";

// Constant speed rather than constant duration: a long list should not race.
const PIXELS_PER_SECOND = 18;
const MIN_SECONDS = 8;

/**
 * Text that scrolls itself when it does not fit, and sits still when it does.
 *
 * Nobody can scroll this screen, so text that overflows would simply be lost.
 * It also gives the board something moving when nothing is happening, which is
 * half the point of having it on a wall.
 */
export function ScrollingText({
  text,
  className = "",
  color,
}: {
  text: string;
  className?: string;
  /** Overrides the inherited colour. The inner element owns `style` already. */
  color?: string;
}) {
  const { ref, overflow } = useOverflow(text);
  const seconds = Math.max(MIN_SECONDS, (overflow / PIXELS_PER_SECOND) * 2);

  return (
    <div
      ref={ref}
      className={`min-h-0 overflow-hidden ${className}`}
      style={color ? { color } : undefined}
    >
      <p
        className="wrap-break-word whitespace-pre-wrap"
        style={
          overflow > 0
            ? {
                animation: `node-scroll ${seconds}s ease-in-out infinite`,
                ["--scroll-distance" as string]: `${overflow}px`,
              }
            : undefined
        }
      >
        {text}
      </p>
    </div>
  );
}
