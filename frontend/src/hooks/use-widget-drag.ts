import { useCallback, useEffect, useRef, useState } from "react";
import { dragged, same, type Grip, type Rect } from "@/lib/drag";

/** A gesture in flight: what was taken hold of, from where, and where it is now. */
type Hold = {
  id: string;
  grip: Grip;
  /** The pointer's position when it went down, in pixels. */
  from: { x: number; y: number };
  start: Rect;
  rect: Rect;
};

/**
 * Dragging and resizing a widget with a pointer.
 *
 * Second-class by design, per `CLAUDE.md`: this is not an editor and nothing is
 * added to the screen to make a widget easier to grab. A widget can be moved by
 * anyone standing at a laptop, and by a session asking for it by name — which is
 * the way it is normally done.
 *
 * The server still owns placement. A gesture is a request: the widget is held
 * where the pointer left it until the server has answered, and then either the
 * socket delivers those same numbers and nothing moves, or the request was
 * refused and the widget goes back where it was. That snap *is* the refusal,
 * shown rather than reported.
 *
 * Holding Alt turns the snapping off, so a widget can be put anywhere at all.
 */
export function useWidgetDrag(
  board: { cols: number; rows: number; width: number; height: number },
  commit: (id: string, rect: Rect) => Promise<unknown>,
): {
  /** Start a gesture. Pass the widget's current rectangle and what was grabbed. */
  grab: (event: React.PointerEvent, id: string, rect: Rect, grip: Grip) => void;
  /** Where to draw a widget: what the pointer says, or what the board says. */
  placed: (id: string, rect: Rect) => Rect;
  /** The widget a pointer is currently holding, if any. */
  holding: string | null;
} {
  // The live gesture is a ref rather than state because a pointer moves far more
  // often than the board needs re-subscribing: only the drawn rectangle is state.
  const hold = useRef<Hold | null>(null);
  const [shown, setShown] = useState<{ id: string; rect: Rect } | null>(null);
  const [holding, setHolding] = useState<string | null>(null);

  const grab = useCallback(
    (event: React.PointerEvent, id: string, rect: Rect, grip: Grip) => {
      // Only the left button, and never over the controls: reaching for the
      // opacity slider should not take the widget with it.
      if (event.button !== 0) return;
      if ((event.target as HTMLElement).closest(".no-drag")) return;
      event.preventDefault();
      hold.current = {
        id,
        grip,
        from: { x: event.clientX, y: event.clientY },
        start: rect,
        rect,
      };
      setShown({ id, rect });
      setHolding(id);
    },
    [],
  );

  useEffect(() => {
    // One cell in pixels. The only place in the gesture that knows the screen
    // has a size at all; everything past here is in columns and rows.
    const cell = { w: board.width / board.cols, h: board.height / board.rows };

    const onMove = (event: PointerEvent) => {
      const held = hold.current;
      if (!held || cell.w <= 0 || cell.h <= 0) return;
      held.rect = dragged(
        held.start,
        held.grip,
        {
          x: (event.clientX - held.from.x) / cell.w,
          y: (event.clientY - held.from.y) / cell.h,
        },
        board,
        !event.altKey,
      );
      setShown({ id: held.id, rect: held.rect });
    };

    const onUp = () => {
      const held = hold.current;
      hold.current = null;
      setHolding(null);
      if (!held) return;
      if (same(held.rect, held.start)) {
        setShown(null);
        return;
      }
      void commit(held.id, held.rect).finally(() => setShown(null));
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [board, commit]);

  const placed = useCallback(
    (id: string, rect: Rect) => (shown?.id === id ? shown.rect : rect),
    [shown],
  );

  return { grab, placed, holding };
}
