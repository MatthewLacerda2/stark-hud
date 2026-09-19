/**
 * The rule about what is on the board, which the backend keeps too.
 *
 * Both sides have to agree or the television draws a board the server does not
 * think exists — a widget in a folded group would be on screen and refuse to be
 * placed anywhere, which is the worst of both.
 *
 * One page's worth of widgets: taking the page off is `lib/pages.test.ts`.
 */
import { describe, expect, it } from "vitest";
import type { GroupState, Item, Payload } from "@/lib/schemas/board";
import { held, isGroup, onBoard } from "@/lib/groups";

function item(
  id: string,
  payload: Payload,
  parent: string | null = null,
): Item {
  return {
    id,
    key: null,
    description: null,
    color: null,
    border: null,
    scale: null,
    payload,
    playback: null,
    x: 0,
    y: 0,
    w: 4,
    h: 3,
    page: "main",
    parent_id: parent,
    pinned: false,
    created_at: "2026-09-01T00:00:00Z",
  };
}

const note: Payload = { kind: "note", text: "x" };
const group = (state: GroupState): Payload => ({ kind: "group", state });

describe("what is actually on the board", () => {
  it("draws an open group's widgets and not the group", () => {
    const board = [item("g", group("open")), item("a", note, "g")];
    expect(onBoard(board).map((i) => i.id)).toEqual(["a"]);
  });

  it("draws a folded group and not its widgets", () => {
    const board = [item("g", group("folded")), item("a", note, "g")];
    expect(onBoard(board).map((i) => i.id)).toEqual(["g"]);
  });

  it("leaves the widgets of a second, open group alone", () => {
    const board = [
      item("g", group("folded")),
      item("a", note, "g"),
      item("h", group("open")),
      item("b", note, "h"),
      item("c", note),
    ];
    expect(onBoard(board).map((i) => i.id)).toEqual(["g", "b", "c"]);
  });

  it("leaves everything outside a group alone", () => {
    const board = [
      item("g", group("folded")),
      item("a", note, "g"),
      item("b", note),
    ];
    expect(onBoard(board).map((i) => i.id)).toEqual(["g", "b"]);
  });

  it("knows a group when it sees one, and what it is holding", () => {
    const g = item("g", group("folded"));
    const board = [g, item("a", note, "g"), item("b", note)];
    expect(isGroup(g)).toBe(true);
    expect(held(g, board).map((i) => i.id)).toEqual(["a"]);
  });
});
