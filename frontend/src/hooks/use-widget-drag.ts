import { useCallback, useEffect, useRef, useState } from "react";
import { dragged, free, landed, same, type Grip, type Rect } from "@/lib/drag";

/** Where a gesture will leave the widget, and whether the board will take it. */
type Landing = {
  /** The rectangle the widget will occupy the moment the hand opens. */
  rect: Rect;
  /** False when that rectangle is the one it started in, because it goes home. */
  fits: boolean;
};

/** A gesture in flight: what was taken hold of, from where, and where it is now. */
type Hold = {
  id: string;
  grip: Grip;
  /** The pointer's position when it went down, in pixels. */
  from: { x: number; y: number };
  start: Rect;
  /** Where the pointer has put it. The widget is drawn here while it is held. */
  rect: Rect;
  /** Where it comes to rest, or `null` when there is nowhere for it to land. */
  rest: Rect | null;
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
 * The server still owns placement. A gesture is a request: the widget goes where
 * the gesture said it would and waits there until the server has answered, and
 * then either the socket delivers those same numbers and nothing moves, or the
 * request was refused and the widget goes back where it was.
 *
 * Holding Alt turns the snapping off, so a widget can be put anywhere at all —
 * anywhere legal, that is. The magnet is a convenience and can be waved away;
 * not overlapping is not.
 *
 * **While it is held, the widget is where the hand is.** `landed` in
 * `lib/drag.ts` runs on every pointer move exactly as it did before — it lines
 * the widget up with what it is beside, slides it off anything it clipped and
 * shrinks it a little if the gap is nearly big enough — but its answer is drawn
 * as a rectangle rather than applied to the widget, and applied when the hand
 * opens. Issue #154 decided the other way round and the owner reversed it on
 * #168 having lived with it: a widget that stops following the pointer and sits
 * at its landing place does not read as a magnet, it reads as the widget being
 * taken away from you.
 *
 * `landing` is that rectangle, and `board-grid.tsx` draws it — the one thing
 * this gesture puts on the screen, and the reason it is allowed to is written
 * beside the component that draws it.
 *
 * A drop with nowhere to go still goes home, which is the one case that should
 * feel like a refusal — but it now says so before the hand opens rather than
 * after. Nothing is sent, because a request the board already knows is an
 * overlap is not a question worth asking; the server is still the judge of
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
  /** The space the held widget is about to take, once it has been asked for. */
  landing: Landing | null;
} {
  // The live gesture is a ref rather than state because a pointer moves far more
  // often than the board needs re-subscribing: only the drawn rectangle is state.
  const hold = useRef<Hold | null>(null);
  const [shown, setShown] = useState<{ id: string; rect: Rect } | null>(null);
  const [landing, setLanding] = useState<Landing | null>(null);
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
        rest: rect,
      };
      setShown({ id, rect });
      // Nothing has been asked for yet, so there is nothing to show: a pointer
      // that goes down and up again on a widget draws no rectangle at all.
      setLanding(null);
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
      const others = seated.current.filter((seat) => seat.id !== held.id);
      // A move attaches to the gaps; a resize does not, and this is the whole
      // of the difference between them.
      //
      // `landed` has three outcomes and two of them move the widget bodily: a
      // slide translates the whole rectangle, and a trim can give up the edge
      // opposite the one being held. Both move the far edge, which `pinched`
      // promises never moves, so a resize that landed would not be a resize.
      // That was already the reason a resize did not snap while it was held,
      // and it turns out to be the same reason on release — the two cannot be
      // separated the way #168 hoped. What a resize gets instead is the half
      // that costs it nothing: whether the board will take what it is holding.
      const rest =
        held.grip === "move"
          ? landed(wanted, others, board, snap)
          : free(wanted, others, board)
            ? wanted
            : null;
      held.rect = wanted;
      held.rest = rest;
      setShown({ id: held.id, rect: wanted });
      // A refused drop previews the seat it is going back to, so the rectangle
      // always answers one question and only one: where this widget will be
      // when the hand opens.
      setLanding({ rect: rest ?? held.start, fits: rest !== null });
    };

    const onUp = () => {
      const held = hold.current;
      hold.current = null;
      setHolding(null);
      setLanding(null);
      if (!held) return;
      const rest = held.rest;
      if (!rest || same(rest, held.start)) {
        setShown(null);
        return;
      }
      // Put the widget where the rectangle was, now, rather than when the
      // server answers: the preview was a promise about the moment the hand
      // opens, and a promise kept a round trip late is a widget that hangs off
      // the pointer and then jumps.
      setShown({ id: held.id, rect: rest });
      void commit(held.id, rest).finally(() => setShown(null));
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

  return { grab, placed, holding, landing };
}
