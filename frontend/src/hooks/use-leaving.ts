import { useCallback, useEffect, useRef, useState } from "react";
import type { Item } from "@/lib/schemas/board";

/**
 * Widgets that have already gone, kept on screen long enough to be seen going.
 *
 * A removal is the one change with nothing left to animate: by the time the
 * board knows about it the widget is not in `items` any more, so there is
 * nothing to draw shrinking. This holds on to the last thing it knew about each
 * departed widget, hands it back as a ghost, and drops it when the ghost says
 * its animation has finished.
 *
 * Nothing here is board state. The board records where things end up, never
 * where they are mid-flight, and a ghost is neither — it is a picture of
 * something that is not there any more, held for exactly as long as its going
 * takes and not a frame more. How long that is belongs to `styles.css`; no
 * number here has to agree with it.
 *
 * The animation reports its own end rather than a timer counting the same
 * duration a second time, which is one number that cannot drift out of step
 * with the design system. `FORGET_MS` is only a stop: an animation that never
 * runs at all — an element never painted, a tab in the background — must not
 * leave a widget on the television that the board says is gone.
 */

/** Far longer than any motion token, because it is a backstop and not a timing. */
const FORGET_MS = 4000;

export function useLeaving(items: Item[]): {
  /** Everything to draw: what is there, and what has just stopped being there. */
  drawn: Item[];
  /** Whether this one is a ghost on its way out. */
  leaving: (id: string) => boolean;
  /** Hand back when a ghost's animation ends, so it can be forgotten. */
  forget: (id: string) => void;
} {
  const [previous, setPrevious] = useState(items);
  const [ghosts, setGhosts] = useState<Item[]>([]);

  // Worked out while rendering, not in an effect afterwards (#208). An effect
  // hears about a departure one commit late, and in that commit the widget is
  // in neither `items` nor `ghosts`: React unmounts it, and then mounts a new
  // copy to play its exit — every widget of every kind rebuilt from scratch
  // only to fade out. A film played its sound again (#204); a mesh built a new
  // WebGL context. Setting state during render re-renders before anything is
  // committed, so the widget never leaves the tree: the same instance goes from
  // live to leaving, and is unmounted once, when it is forgotten.
  if (items !== previous) {
    setPrevious(items);
    const here = new Set(items.map((item) => item.id));
    const gone = previous.filter((item) => !here.has(item.id));
    if (gone.length > 0) {
      const leaving = new Set(gone.map((item) => item.id));
      setGhosts((current) => [
        ...current.filter((ghost) => !leaving.has(ghost.id)),
        ...gone,
      ]);
    }
  }

  // The backstop, one per ghost and counted from when it became one, so a
  // steady stream of departures never postpones an older ghost's end.
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  useEffect(() => {
    const running = timers.current;
    const held = new Set(ghosts.map((ghost) => ghost.id));
    for (const [id, stop] of running) {
      if (held.has(id)) continue;
      clearTimeout(stop);
      running.delete(id);
    }
    for (const id of held) {
      if (running.has(id)) continue;
      running.set(
        id,
        setTimeout(() => {
          running.delete(id);
          setGhosts((current) => current.filter((ghost) => ghost.id !== id));
        }, FORGET_MS),
      );
    }
  }, [ghosts]);
  useEffect(() => {
    const running = timers.current;
    return () => running.forEach((stop) => clearTimeout(stop));
  }, []);

  const forget = useCallback((id: string) => {
    setGhosts((current) => current.filter((ghost) => ghost.id !== id));
  }, []);

  // A widget that came back before its ghost was forgotten is drawn once, as
  // itself. Folding a group and unfolding it again inside a second is exactly
  // that, and two of the same widget is worse than no animation at all.
  const here = new Set(items.map((item) => item.id));
  const held = ghosts.filter((ghost) => !here.has(ghost.id));

  return {
    drawn: [...items, ...held],
    leaving: (id: string) => !here.has(id),
    forget,
  };
}
