/**
 * What stops being worth drawing when a widget takes the whole board.
 *
 * The rule is about cost, not tidiness: two 1080p videos were being decoded at
 * once and only one of them was on screen. So what this asks of every kind is
 * whether the board would still be paying for it, and of a player whether it
 * survives — a record playing in a corner is not covered by a film over it, and
 * unmounting it would silence it, lose its place and tell the server it stopped.
 */
import { describe, expect, it } from "vitest";
import type { Item, ItemKind, Payload } from "@/lib/schemas/board";
import { drawn, maximisedIn } from "@/lib/maximised";

/** Enough of an item for these two questions; the rest is placement. */
function item(id: string, payload: Payload): Item {
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
    h: 4,
    page: "main",
    parent_id: null,
    created_at: "2026-09-01T00:00:00Z",
  };
}

function media(maximised: boolean, muted = false): Payload {
  return {
    kind: "media",
    tracks: [],
    index: 0,
    playing: true,
    loop: false,
    muted,
    maximised,
    captions: false,
    seconds: 0,
    title: null,
  };
}

const clock: Payload = { kind: "clock" };
// A clip put up to be looked at rather than listened to. It used to be a widget
// kind of its own; now it is a player with one thing in it and nothing to hear.
const loop: Payload = media(false, true);

describe("the widget with the whole board", () => {
  it("is the media widget asking for it, and nothing else ever asks", () => {
    const film = item("film", media(true));
    expect(maximisedIn([item("clock", clock), film])).toBe(film);
    expect(
      maximisedIn([item("clock", clock), item("song", media(false))]),
    ).toBe(undefined);
  });
});

describe("what the grid still draws underneath", () => {
  const film = item("film", media(true));

  it("draws everything when nobody has the board", () => {
    for (const covered of [clock, loop, media(false)]) {
      expect(drawn(item("other", covered), undefined)).toBe(true);
    }
  });

  it("stops drawing what a maximised widget covers", () => {
    const kinds: [ItemKind, Payload][] = [
      ["clock", clock],
      // A muted player is covered like anything else: it has nothing to be
      // heard, so the only thing it was costing was a decode for nobody.
      ["media", loop],
      ["note", { kind: "note", text: "hello" }],
    ];
    for (const [kind, payload] of kinds) {
      expect([kind, drawn(item(kind, payload), film)]).toEqual([kind, false]);
    }
  });

  it("keeps a player that can be heard, because sound is not covered", () => {
    expect(drawn(item("song", media(false)), film)).toBe(true);
  });

  it("leaves the maximised widget's own slot empty, as it always did", () => {
    // It is drawn over the board instead. Drawing it twice would be two players
    // on the same file, which is the bug this whole change is about.
    expect(drawn(film, film)).toBe(false);
  });
});
