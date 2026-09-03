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
 * something that is not there any more, held for a fifth of a second.
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
  const seen = useRef(new Map<string, Item>());
  const [ghosts, setGhosts] = useState<Item[]>([]);

  useEffect(() => {
    const here = new Map(items.map((item) => [item.id, item] as const));
    const gone = [...seen.current.values()].filter(
      (item) => !here.has(item.id),
    );
    seen.current = here;
    if (gone.length === 0) return;

    setGhosts((current) => [...current, ...gone]);
    const ids = new Set(gone.map((item) => item.id));
    const stop = setTimeout(
      () => setGhosts((current) => current.filter((g) => !ids.has(g.id))),
      FORGET_MS,
    );
    return () => clearTimeout(stop);
  }, [items]);

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
