import type { Item } from "@/lib/schemas/board";

/**
 * What is actually on the board, out of everything the server sent.
 *
 * The same rule the backend keeps in `services/groups.py`, and it has to be the
 * same one: an open group is a bracket rather than a pane, so it takes up
 * nothing and draws nothing while its widgets sit where they always did. Folded,
 * the trade goes the other way — its widgets come off the board and the group
 * draws in their place. Away, neither half is here: the widgets come off and
 * nothing is drawn, because that group is a screen the board is not showing.
 *
 * Kept here rather than in the board component because it is a fact about the
 * board and not about how one is drawn.
 */

/** Whether this widget is one that holds widgets. */
export function isGroup(item: Item): boolean {
  return item.payload.kind === "group";
}

/** The groups whose widgets are off the board: folded and away alike. */
function closed(items: Item[]): Set<string> {
  return new Set(
    items
      .filter((i) => i.payload.kind === "group" && i.payload.state !== "open")
      .map((i) => i.id),
  );
}

/** The groups that are drawn at all, which is only the folded ones. */
function shelved(items: Item[]): Set<string> {
  return new Set(
    items
      .filter((i) => i.payload.kind === "group" && i.payload.state === "folded")
      .map((i) => i.id),
  );
}

/** The widgets to draw: everything except what is off the board, and open groups. */
export function onBoard(items: Item[]): Item[] {
  const off = closed(items);
  const drawn = shelved(items);
  return items.filter(
    (i) =>
      !(i.parent_id !== null && off.has(i.parent_id)) &&
      (!isGroup(i) || drawn.has(i.id)),
  );
}

/** What a folded group is holding, oldest first. */
export function held(group: Item, items: Item[]): Item[] {
  return items.filter((i) => i.parent_id === group.id);
}
