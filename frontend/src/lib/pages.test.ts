/**
 * The rule about which page is on the television, which the backend keeps too.
 *
 * Both sides have to agree or the board draws widgets the server has already
 * given the room away for: every widget is sent whatever page it is on, and
 * only this decides which of them exist as far as the screen is concerned.
 */
import { describe, expect, it } from "vitest";
import type { Item, Payload } from "@/lib/schemas/board";
import { onBoard } from "@/lib/groups";
import { onPage } from "@/lib/pages";

function item(id: string, page: string, parent: string | null = null): Item {
  return {
    id,
    key: null,
    description: null,
    color: null,
    border: null,
    scale: null,
    payload: { kind: "note", text: "x" } as Payload,
    playback: null,
    x: 0,
    y: 0,
    w: 4,
    h: 3,
    page,
    parent_id: parent,
    created_at: "2026-09-01T00:00:00Z",
  };
}

describe("which widgets are on the board that is showing", () => {
  it("draws the page it is turned to and nothing else", () => {
    const board = [item("a", "main"), item("b", "planning"), item("c", "main")];
    expect(onPage(board, "main").map((i) => i.id)).toEqual(["a", "c"]);
    expect(onPage(board, "planning").map((i) => i.id)).toEqual(["b"]);
  });

  it("draws an empty board for a page nobody has put anything on", () => {
    // How a new page starts, and what the television shows while it is built.
    expect(onPage([item("a", "main")], "guests")).toEqual([]);
  });

  it("takes the page off before the groups, never the other way round", () => {
    // A group is a handful of widgets on one page. Its folded state says what
    // is drawn *there*, and says nothing at all about a board it is not on.
    const board = [
      item("a", "main"),
      { ...item("g", "planning"), payload: { kind: "group", state: "folded" } },
      item("b", "planning", "g"),
    ] as Item[];
    expect(onBoard(onPage(board, "main")).map((i) => i.id)).toEqual(["a"]);
    expect(onBoard(onPage(board, "planning")).map((i) => i.id)).toEqual(["g"]);
  });
});
