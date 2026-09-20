import { useCallback, useEffect, useRef, useState } from "react";
import { dragged, landed, same, type Grip, type Rect } from "@/lib/drag";

/** A gesture in flight: what was taken hold of, from where, and where it is now. */
type Hold = {
  id: string;
  grip: Grip;
  /** The pointer's position when it went down, in pixels. */
  from: { x: number; y: number };
  start: Rect;
  rect: Rect;
  /** Whether `rect` is somewhere the board could actually take it. */
  fits: boolean;
};

/** A widget as a gesture sees one: four numbers and which widget they belong to. */
type Seat = Rect & { id: string };

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
 * Holding Alt turns the snapping off, so a widget can be put anywhere at all —
 * anywhere legal, that is. The magnet is a convenience and can be waved away;
 * not overlapping is not.
 *
 * A widget held over a gap attaches to it rather than waiting to be refused:
 * `landed` in `lib/drag.ts` aligns it to what it is beside, slides it off
 * anything it clipped and shrinks it a little if the gap is nearly big enough,
 * and it does all of that while the pointer is still down. So letting go
 * changes nothing, which is what makes it a magnet rather than a jump. Nothing
 * is drawn for any of it: the widget is its own preview, and the television has
 * no pointer to draw for anyway.
 *
 * A drop with nowhere to go is the one case left, and it is the refusal: the
 * widget follows the pointer over whatever it was put on and springs back when
 * released. Nothing is sent, because a request the board already knows is an
 * overlap is not a question worth asking — the server is still the judge of
 * every rectangle that is asked about, and it still refuses.
 */
export function useWidgetDrag(
  board: { cols: number; rows: number; width: number; height: number },
  commit: (id: string, rect: Rect) => Promise<unknown>,
  /** Every widget on the board, the held one included: what it can bump into. */
  seats: Seat[],
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
  // The board changes under the pointer — a panel refreshes, a session moves
  // something — and the gesture wants the latest of it without re-subscribing a
  // pointer handler every time a clock ticks.
  const seated = useRef(seats);
  useEffect(() => {
    seated.current = seats;
  }, [seats]);

  const grab = useCallback(
    (event: React.PointerEvent, id: string, rect: Rect, grip: Grip) => {
      // Only the left button, and never over anything marked `no-drag`: a
      // control inside a widget should not take the widget with it.
      if (event.button !== 0) return;
      if ((event.target as HTMLElement).closest(".no-drag")) return;
      event.preventDefault();
      // The grips sit inside the widget, so a pointer landing on one also
      // reaches the widget itself on the way up. Without this the edge gesture
      // was started and then immediately replaced by a move, and resizing was
      // not merely broken but impossible — every grab became a drag.
      event.stopPropagation();
      hold.current = {
        id,
        grip,
        from: { x: event.clientX, y: event.clientY },
        start: rect,
        rect,
        fits: true,
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
      const snap = !event.altKey;
      const wanted = dragged(
        held.start,
        held.grip,
        {
          x: (event.clientX - held.from.x) / cell.w,
          y: (event.clientY - held.from.y) / cell.h,
        },
        board,
        snap,
      );
      // Moving only. A resize is somebody working on one widget rather than
      // putting it somewhere, and an edge that shrank itself out of the way
      // would be fighting the hand that is dragging it.
      const rest =
        held.grip === "move"
          ? landed(
              wanted,
              seated.current.filter((seat) => seat.id !== held.id),
              board,
              snap,
            )
          : wanted;
      held.rect = rest ?? wanted;
      held.fits = rest !== null;
      setShown({ id: held.id, rect: held.rect });
    };

    const onUp = () => {
      const held = hold.current;
      hold.current = null;
      setHolding(null);
      if (!held) return;
      if (!held.fits || same(held.rect, held.start)) {
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
