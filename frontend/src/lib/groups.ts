import type { Item } from "@/lib/schemas/board";

/**
 * What is actually on the board, out of everything the server sent.
 *
 * The same rule the backend keeps in `services/groups.py`, and it has to be the
 * same one: an open group is a bracket rather than a pane, so it takes up
 * nothing and draws nothing while its widgets sit where they always did. Closed,
 * the trade goes the other way — its widgets come off the board and the group
 * draws in their place.
 *
 * Kept here rather than in the board component because it is a fact about the
 * board and not about how one is drawn.
 */

/** Whether this widget is one that holds widgets. */
export function isGroup(item: Item): boolean {
  return item.payload.kind === "group";
}

/** The groups that are currently folded. */
function shut(items: Item[]): Set<string> {
  return new Set(
    items
      .filter((i) => i.payload.kind === "group" && !i.payload.open)
      .map((i) => i.id),
  );
}

/** The widgets to draw: everything except what is folded away, and open groups. */
export function onBoard(items: Item[]): Item[] {
  const folded = shut(items);
  return items.filter(
    (i) =>
      !(i.parent_id !== null && folded.has(i.parent_id)) &&
      (!isGroup(i) || folded.has(i.id)),
  );
}

/** What a folded group is holding, oldest first. */
export function held(group: Item, items: Item[]): Item[] {
  return items.filter((i) => i.parent_id === group.id);
}
