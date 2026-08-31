import { cn } from "@/lib/utils";
import type { Background as BackgroundType } from "@/lib/schemas/board";

/**
 * A looping video behind the grid, always muted.
 *
 * 11px: enough to stop the video competing with the tiles, not so much that
 * it stops being a picture of something.
 *
 * Keyed on the path so swapping videos remounts the element: the URL never
 * changes, so without the key the browser would keep playing the old file.
 *
 * Blurring scales up slightly, because a blur samples past the edges and would
 * otherwise leave a soft transparent border.
 */
export function Background({
  background,
}: {
  background: BackgroundType | null;
}) {
  if (!background) return null;
  return (
    <video
      key={background.path}
      src="/api/v1/media/background"
      autoPlay
      loop
      muted
      playsInline
      className={cn(
        "absolute inset-0 size-full object-cover",
        background.blur && "scale-105 blur-[11px]",
      )}
    />
  );
}
