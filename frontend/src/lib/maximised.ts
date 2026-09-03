import type { Item } from "@/lib/schemas/board";

/**
 * What a widget with the whole board hides, and what the board does about it.
 *
 * A covered widget still costs whatever it costs. The board sits on a looping
 * 1080p video and a maximised film is another one on top of it, so the machine
 * was decoding two streams and could only ever show one — around 224% of a core
 * for a picture nobody could look at. Being invisible is not being free, and
 * this is where the board works out what has stopped being worth drawing.
 */

/**
 * The widget that has been given the whole board, if one has.
 *
 * It is drawn in a layer over the board rather than resized into it. The board
 * is finite and never overlaps, so a widget asking for all of it would have to
 * push every other widget off a board that cannot scroll — and it has to be able
 * to give the room back. This way its own place stays exactly where it was,
 * empty, and nothing moves underneath it.
 *
 * Only ever asked about what is on the board. A maximised widget folded away
 * inside a group is not on screen at all, and covers nothing.
 */
export function maximisedIn(items: Item[]): Item | undefined {
  return items.find((i) => i.payload.kind === "media" && i.payload.maximised);
}

/**
 * Whether the board still draws this widget.
 *
 * Nothing on the board is visible while a widget has all of it, so the board
 * stops building them: a looping video widget behind an opaque one decodes every
 * frame for nobody, and a chart redraws itself into the dark. They are cheap to
 * put back — everything they show comes off the board, not out of themselves —
 * so leaving maximised finds them exactly as they were.
 *
 * A player is the exception, and stays mounted. It may be sounding, and sound is
 * not covered by anything: the record playing in the corner has to go on playing
 * while a film is watched. Taking it out of the tree would also lose where it had
 * got to and tell the server it had stopped, which is a worse bargain than the
 * picture it wastes.
 *
 * The maximised widget itself is drawn over the board instead, so its own place
 * is empty for the same reason it always was.
 */
export function drawn(item: Item, maximised: Item | undefined): boolean {
  if (!maximised) return true;
  if (item.id === maximised.id) return false;
  return item.payload.kind === "media";
}
