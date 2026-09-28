import { describe, expect, it } from "vitest";
import { GAP, labelOf, placeLabels } from "@/lib/mesh-labels";

describe("labelOf", () => {
  it("reads the label a node's extras carry", () => {
    expect(labelOf({ label: "Paris" })).toBe("Paris");
    expect(labelOf({ label: "  layer 5  " })).toBe("layer 5");
  });

  it("takes a number as its words", () => {
    expect(labelOf({ label: 5 })).toBe("5");
  });

  it("finds nothing on a node with no label, or an empty one", () => {
    expect(labelOf({})).toBeNull();
    expect(labelOf({ name: "fan" })).toBeNull();
    expect(labelOf({ label: "   " })).toBeNull();
    expect(labelOf({ label: { text: "x" } })).toBeNull();
    expect(labelOf({ label: Number.NaN })).toBeNull();
    expect(labelOf(null)).toBeNull();
    expect(labelOf(undefined)).toBeNull();
  });
});

describe("placeLabels", () => {
  const word = { w: 40, h: 10 };
  const gap = word.h * GAP;

  it("writes a word to the right of its point, centred on it", () => {
    expect(placeLabels([{ x: 100, y: 50 }], [word], 200, 100)).toEqual([
      { x: 100 + gap, y: 45 },
    ]);
  });

  it("turns to the left of the point against the right edge", () => {
    expect(placeLabels([{ x: 180, y: 50 }], [word], 200, 100)).toEqual([
      { x: 180 - gap - 40, y: 45 },
    ]);
  });

  it("keeps a word inside the widget top and bottom", () => {
    const [top, bottom] = placeLabels(
      [
        { x: 10, y: 1 },
        { x: 100, y: 99 },
      ],
      [word, word],
      200,
      100,
    );
    expect(top?.y).toBe(0);
    expect(bottom?.y).toBe(90);
  });

  it("draws nothing for a point off the widget or behind the camera", () => {
    expect(
      placeLabels(
        [{ x: -1, y: 50 }, { x: 50, y: 101 }, null],
        [word, word, word],
        200,
        100,
      ),
    ).toEqual([null, null, null]);
  });

  it("draws nothing for a word wider than the widget", () => {
    expect(
      placeLabels([{ x: 10, y: 50 }], [{ w: 300, h: 10 }], 200, 100),
    ).toEqual([null]);
  });

  it("lets the first label in the file win when two crowd", () => {
    const crowded = [
      { x: 50, y: 50 },
      { x: 55, y: 52 },
    ];
    expect(placeLabels(crowded, [word, word], 200, 100)).toEqual([
      { x: 50 + gap, y: 45 },
      null,
    ]);
    // The other order is the other winner: it is the file that decides.
    expect(placeLabels([...crowded].reverse(), [word, word], 200, 100)).toEqual(
      [{ x: 55 + gap, y: 47 }, null],
    );
  });

  it("keeps words a gap apart, not merely apart", () => {
    // One line plus less than the gap below: the boxes do not overlap, but the
    // words would sit on top of each other with no air between them.
    const close = placeLabels(
      [
        { x: 50, y: 50 },
        { x: 50, y: 50 + word.h + gap / 2 },
      ],
      [word, word],
      200,
      100,
    );
    expect(close[1]).toBeNull();
    const clear = placeLabels(
      [
        { x: 50, y: 50 },
        { x: 50, y: 50 + word.h + gap * 1.5 },
      ],
      [word, word],
      200,
      100,
    );
    expect(clear[1]).not.toBeNull();
  });

  it("does not let a hidden label hide anything else", () => {
    const [first, second, third] = placeLabels(
      [
        { x: 50, y: 50 },
        { x: 60, y: 50 },
        { x: 97, y: 50 },
      ],
      [word, word, word],
      200,
      100,
    );
    expect(first).not.toBeNull();
    expect(second).toBeNull();
    // Clear of the first, though it would have touched the second.
    expect(third).not.toBeNull();
  });
});
