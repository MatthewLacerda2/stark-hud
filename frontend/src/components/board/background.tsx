import { useEffect, useRef } from "react";
import { backgroundUrl } from "@/lib/api/media";
import { cn } from "@/lib/utils";
import type { Background as BackgroundType } from "@/lib/schemas/board";

/**
 * A looping video behind the grid, always muted.
 *
 * It plays the board-ready copy when the backend has made one, and the original
 * until then. The copy is a quarter of the pixels at four fifths of the frames:
 * on a machine that decodes h264 in software, the pixels are most of what the
 * background costs, and under the blur nobody can see which one is playing.
 * Without a copy nothing changes from before copies existed.
 *
 * 9px: enough to stop the video competing with the widgets, not so much that
 * it stops being a picture of something. The blur stays here, on the copy as
 * on the original, because here it is nine pixels on every screen; baked into
 * the copy it could only be right for one screen width.
 *
 * Keyed on the path so swapping videos remounts the element.
 *
 * Blurring scales up slightly, because a blur samples past the edges and would
 * otherwise leave a soft transparent border.
 *
 * When the copy arrives the element is already playing the original, and swaps
 * to it where it was rather than from the top of the loop: the two are the same
 * picture, so a jump back to the start would be the only sign anything happened.
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
  // Where this path's loop had got to, for the moment the copy replaces it.
  const reached = useRef({ path: "", at: 0 });
  const path = background?.path ?? null;
  const copy = background?.board_copy ?? null;
  const source = backgroundUrl(copy);

  // The source is a dependency as well as the flag, because a background set —
  // or a copy arriving — while something is maximised arrives autoplaying and
  // has to be stopped. Pausing is unconditional for that reason: it also clears
  // the autoplay the browser is about to act on, and pausing something already
  // paused is silent.
  useEffect(() => {
    const video = element.current;
    if (!video) return;
    if (covered) {
      video.pause();
      return;
    }
    if (video.paused) void video.play().catch(() => {});
  }, [covered, path, source]);

  if (!background) return null;
  return (
    <video
      ref={element}
      key={background.path}
      src={source}
      autoPlay
      loop
      muted
      playsInline
      onTimeUpdate={(event) => {
        // Loading a new source rewinds to zero and says so with a timeupdate
        // before it has anything to show. That zero is not where the loop was.
        if (event.currentTarget.readyState === HTMLMediaElement.HAVE_NOTHING)
          return;
        reached.current = {
          path: background.path,
          at: event.currentTarget.currentTime,
        };
      }}
      onLoadedMetadata={(event) => {
        if (reached.current.path === background.path) {
          event.currentTarget.currentTime = reached.current.at;
        }
      }}
      className={cn(
        "absolute inset-0 size-full object-cover",
        background.blur && "scale-105 blur-[9px]",
      )}
    />
  );
}
