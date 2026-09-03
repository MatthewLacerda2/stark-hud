import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { Background as BackgroundType } from "@/lib/schemas/board";

/**
 * A looping video behind the grid, always muted.
 *
 * 9px: enough to stop the video competing with the widgets, not so much that
 * it stops being a picture of something.
 *
 * Keyed on the path so swapping videos remounts the element: the URL never
 * changes, so without the key the browser would keep playing the old file.
 *
 * Blurring scales up slightly, because a blur samples past the edges and would
 * otherwise leave a soft transparent border.
 *
 * It stops while a widget has the whole board. This is the only thing on the
 * board that is always behind everything, so it is also the only thing that can
 * be completely hidden and go on costing a core to decode — which is what it was
 * doing under a maximised film.
 *
 * Paused, never unmounted. The next thing that happens to a hidden background is
 * that it becomes visible again, and a remount would fetch the file afresh and
 * start the loop from the top. A pause carries on from where it stopped, which
 * is what makes leaving maximised look like nothing happened.
 */
export function Background({
  background,
  covered,
}: {
  background: BackgroundType | null;
  covered: boolean;
}) {
  const element = useRef<HTMLVideoElement>(null);
  const path = background?.path ?? null;

  // The path is a dependency as well as the flag, because a background set while
  // something is already maximised arrives autoplaying and has to be stopped.
  // Pausing is unconditional for that reason: it also clears the autoplay the
  // browser is about to act on, and pausing something already paused is silent.
  useEffect(() => {
    const video = element.current;
    if (!video) return;
    if (covered) {
      video.pause();
      return;
    }
    if (video.paused) void video.play().catch(() => {});
  }, [covered, path]);

  if (!background) return null;
  return (
    <video
      ref={element}
      key={background.path}
      src="/api/v1/media/background"
      autoPlay
      loop
      muted
      playsInline
      className={cn(
        "absolute inset-0 size-full object-cover",
        background.blur && "scale-105 blur-[9px]",
      )}
    />
  );
}
