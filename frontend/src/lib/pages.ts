import type { Item } from "@/lib/schemas/board";

/**
 * Which widgets belong to the board that is showing.
 *
 * The server sends every widget on every page and says which page is up, rather
 * than sending one page's worth: a widget on another page goes on taking writes
 * the whole time, and a page that was streamed away and back would have to be
 * fetched again to come back current. So the page turn is one field changing,
 * and this is the rule that reads it.
 *
 * The same rule the backend keeps in `services/pages.py`, and it has to be the
 * same one — the two disagreeing is a widget on the television that the server
 * thinks is not there.
 */

/** The widgets on the page the board is turned to. */
export function onPage(items: Item[], showing: string): Item[] {
  return items.filter((i) => i.page === showing);
}
