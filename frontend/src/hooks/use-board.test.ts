/**
 * The join between the socket and what a widget is told.
 *
 * `item.waking` is the one event that changes nothing about the board, so it is
 * also the one that is easiest to drop on the floor without anybody noticing:
 * the page would still be correct, it would just never acknowledge anything.
 */
import { describe, expect, it } from "vitest";
import type {
  BoardEvent,
  Item,
  Notification,
  Spoken,
} from "@/lib/schemas/board";
import { reduceBoard } from "@/hooks/use-board";

const EMPTY = {
  items: [] as Item[],
  background: null,
  notifications: [],
  page: 0,
  wakes: {} as Record<string, number>,
  spoken: [] as Spoken[],
};

function note(id: string, text: string): Item {
  return {
    id,
    key: null,
    description: null,
    opacity: null,
    background: null,
    color: null,
    border: null,
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

function alert(id: string, title: string): Notification {
  return {
    id,
    title,
    body: null,
    source: null,
    level: "info",
    icon: null,
    title_color: null,
    body_color: null,
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

/**
 * The inbox on a board nobody reloads.
 *
 * These three arms of the event union went unhandled for as long as they
 * existed, and the symptom was invisible: notifications arrived in the snapshot
 * on page load, so an inbox that never updated looked exactly like an inbox
 * with nothing new in it. On a television nobody stands at, that is the whole
 * of the feature failing quietly.
 */
describe("what the inbox hears while the page stays open", () => {
  it("shows a notification that arrives after the page loaded", () => {
    const state = play({
      event: "notification.created",
      data: alert("a", "one"),
    });
    expect(state.notifications.map((n) => n.id)).toEqual(["a"]);
  });

  it("puts the newest at the front, which is the end the widget reads from", () => {
    const state = play(
      { event: "notification.created", data: alert("a", "one") },
      { event: "notification.created", data: alert("b", "two") },
    );
    expect(state.notifications.map((n) => n.id)).toEqual(["b", "a"]);
  });

  it("takes away only the one that was dismissed", () => {
    const state = play(
      { event: "notification.created", data: alert("a", "one") },
      { event: "notification.created", data: alert("b", "two") },
      { event: "notification.removed", data: { id: "a" } },
    );
    expect(state.notifications.map((n) => n.id)).toEqual(["b"]);
  });

  it("empties on a clear, and leaves the board alone doing it", () => {
    const state = play(
      { event: "item.created", data: note("w", "a widget") },
      { event: "notification.created", data: alert("a", "one") },
      { event: "notifications.cleared", data: { removed: 1 } },
    );
    expect(state.notifications).toEqual([]);
    expect(state.items.map((i) => i.id)).toEqual(["w"]);
  });
});
