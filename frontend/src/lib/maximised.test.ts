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
function item(id: string, payload: Payload, page = 0): Item {
  return {
    id,
    key: null,
    description: null,
    opacity: null,
    background: null,
    color: null,
    border: null,
    scale: null,
    payload,
    playback: null,
    page,
    x: 0,
    y: 0,
    w: 4,
    h: 4,
    parent_id: null,
    pinned: false,
    created_at: "2026-09-01T00:00:00Z",
  };
}

function media(maximised: boolean): Payload {
  return {
    kind: "media",
    tracks: [],
    index: 0,
    playing: true,
    loop: false,
    muted: false,
    maximised,
    captions: false,
    seconds: 0,
    title: null,
  };
}

const clock: Payload = { kind: "clock" };
const video: Payload = {
  kind: "video",
  path: "/mnt/d_drive/Video/loop.mp4",
  autoplay: true,
  loop: true,
  muted: true,
};

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
    for (const covered of [clock, video, media(false)]) {
      expect(drawn(item("other", covered), undefined)).toBe(true);
    }
  });

  it("stops drawing what a maximised widget covers", () => {
    const kinds: [ItemKind, Payload][] = [
      ["clock", clock],
      ["video", video],
      ["note", { kind: "note", text: "hello", color: null }],
    ];
    for (const [kind, payload] of kinds) {
      expect([kind, drawn(item(kind, payload), film)]).toEqual([kind, false]);
    }
  });

  it("keeps a player, because sound is not covered by anything", () => {
    expect(drawn(item("song", media(false)), film)).toBe(true);
  });

  it("leaves the maximised widget's own slot empty, as it always did", () => {
    // It is drawn over the board instead. Drawing it twice would be two players
    // on the same file, which is the bug this whole change is about.
    expect(drawn(film, film)).toBe(false);
  });
});
