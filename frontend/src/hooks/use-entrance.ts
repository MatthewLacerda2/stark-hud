import { useEffect, useRef } from "react";
import type { Rect } from "@/lib/drag";
import { entrance, type Entrance } from "@/lib/entrance";
import type { Item } from "@/lib/schemas/board";

/**
 * Which way each widget came in, decided once and then left alone.
 *
 * How a widget arrived is a fact about the moment it arrived. `lib/entrance.ts`
 * can answer the question at any time — it is a pure function of the board —
 * but asking it twice about the same arrival is answering something that was
 * already answered, and the second answer can differ from the first.
 *
 * That is not theoretical. The answer becomes a class name, a class name is
 * part of `className`, and changing one restarts a CSS animation from zero: a
 * widget three quarters of the way in from the left would begin again from
 * nothing in the middle of the board. The flight's starting point can move the
 * same way without restarting anything, which looks like the widget changing
 * its mind mid-air. Either needs only a second widget to land in the first's
 * corridor inside 700ms — which is what `arrange` does, and what a board being
 * rebuilt does, so it is an ordinary Tuesday rather than a corner case.
 *
 * So an arrival is decided on the widget's first render and read from here
 * afterwards. A departure is decided the same way but separately, at the moment
 * of removal, because a widget should leave by a way that is clear of the board
 * as it stands then rather than as it stood when the widget turned up.
 *
 * Nothing here is board state — it is not even one render's worth of it. It is
 * the answer to a question that was asked while a widget was being drawn for
 * the first time, kept until that widget is gone.
 */
export function useEntrance(
  /** The board as it stands: what a corridor has to be clear of. */
  items: Item[],
  /** Everything drawn, ghosts included, so a widget that goes is forgotten. */
  drawn: Item[],
  cols: number,
  rows: number,
): (item: Item, rect: Rect, going: boolean) => Entrance {
  const arriving = useRef(new Map<string, Entrance>());
  const leaving = useRef(new Map<string, Entrance>());

  // After the render, not during it: a widget still on screen must keep its
  // answer even if React throws this render away. A widget that comes back —
  // an unfolded group is exactly that — arrives afresh, against the board it is
  // coming back to.
  useEffect(() => {
    const here = new Set(drawn.map((item) => item.id));
    for (const decided of [arriving.current, leaving.current]) {
      for (const id of [...decided.keys()]) {
        if (!here.has(id)) decided.delete(id);
      }
    }
  }, [drawn]);

  return (item, rect, going) => {
    const decided = going ? leaving.current : arriving.current;
    const known = decided.get(item.id);
    if (known) return known;

    const flight = entrance(
      rect,
      items.filter((other) => other.id !== item.id),
      { cols, rows },
    );
    decided.set(item.id, flight);
    return flight;
  };
}
