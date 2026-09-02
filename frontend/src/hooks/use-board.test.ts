/**
 * The join between the socket and what a widget is told.
 *
 * `item.waking` is the one event that changes nothing about the board, so it is
 * also the one that is easiest to drop on the floor without anybody noticing:
 * the page would still be correct, it would just never acknowledge anything.
 */
import { describe, expect, it } from "vitest";
import type { BoardEvent, Item } from "@/lib/schemas/board";
import { reduceBoard } from "@/hooks/use-board";

const EMPTY = {
  items: [] as Item[],
  background: null,
  notifications: [],
  page: 0,
  wakes: {} as Record<string, number>,
};

function note(id: string, text: string): Item {
  return {
    id,
    key: null,
    description: null,
    opacity: null,
    background: null,
    color: null,
    scale: null,
    payload: { kind: "note", text, color: null },
    playback: null,
    page: 0,
    x: 0,
    y: 0,
    w: 6,
    h: 4,
    parent_id: null,
    pinned: false,
    created_at: "2026-09-01T00:00:00Z",
  };
}

/** Play a run of events through the board, the way the socket delivers them. */
function play(...events: BoardEvent[]) {
  return events.reduce(reduceBoard, EMPTY);
}

describe("a widget told work is coming", () => {
  it("is counted without anything about the board changing", () => {
    const state = play(
      { event: "item.created", data: note("a", "hello") },
      { event: "item.waking", data: { id: "a" } },
    );

    expect(state.wakes).toEqual({ a: 1 });
    expect(state.items[0].payload).toEqual({
      kind: "note",
      text: "hello",
      color: null,
    });
  });

  it("is counted again rather than flagged, so a long job can hold twice", () => {
    const state = play(
      { event: "item.waking", data: { id: "a" } },
      { event: "item.waking", data: { id: "a" } },
    );

    expect(state.wakes).toEqual({ a: 2 });
  });

  it("stops waiting the moment the write it was promised lands", () => {
    const state = play(
      { event: "item.created", data: note("a", "…") },
      { event: "item.waking", data: { id: "a" } },
      { event: "item.updated", data: note("a", "the answer") },
    );

    expect(state.wakes).toEqual({});
  });

  it("keeps waiting when somebody else's widget is written to", () => {
    const state = play(
      { event: "item.waking", data: { id: "a" } },
      { event: "item.updated", data: note("b", "unrelated") },
    );

    expect(state.wakes).toEqual({ a: 1 });
  });

  it("forgets everything a reconnection could not know it was still waiting for", () => {
    const state = play(
      { event: "item.waking", data: { id: "a" } },
      {
        event: "board.snapshot",
        data: {
          items: [note("a", "hello")],
          background: null,
          notifications: [],
          page: 0,
        },
      },
    );

    expect(state.wakes).toEqual({});
  });
});
