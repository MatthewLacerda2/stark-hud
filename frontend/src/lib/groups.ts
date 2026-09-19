import type { Item } from "@/lib/schemas/board";

/**
 * What is actually on the board, out of one page's worth of widgets.
 *
 * The same rule the backend keeps in `services/groups.py`, and it has to be the
 * same one: an open group is a bracket rather than a pane, so it takes up
 * nothing and draws nothing while its widgets sit where they always did.
 * Folded, the trade goes the other way — its widgets come off the board and the
 * group draws in their place.
 *
 * One page at a time: `lib/pages.ts` takes the page off first, because a group
 * is a handful of widgets on a page and never a page of its own.
 *
 * Kept here rather than in the board component because it is a fact about the
 * board and not about how one is drawn.
 */

/** Whether this widget is one that holds widgets. */
export function isGroup(item: Item): boolean {
  return item.payload.kind === "group";
}

/**
 * The folded groups, which are both halves of the trade at once: exactly the
 * groups that are drawn, and exactly the groups whose widgets are not.
 */
function folded(items: Item[]): Set<string> {
  return new Set(
    items
      .filter((i) => i.payload.kind === "group" && i.payload.state === "folded")
      .map((i) => i.id),
  );
}

/** The widgets to draw: everything except what is folded away, and open groups. */
export function onBoard(items: Item[]): Item[] {
  const shut = folded(items);
  return items.filter(
    (i) =>
      !(i.parent_id !== null && shut.has(i.parent_id)) &&
      (!isGroup(i) || shut.has(i.id)),
  );
}

/** What a folded group is holding, oldest first. */
export function held(group: Item, items: Item[]): Item[] {
  return items.filter((i) => i.parent_id === group.id);
}
