/**
 * The glass's dirt: one picture made once, and where each pane starts in it.
 *
 * What it looks like is judged on the board. What can be held here is that the
 * picture is the same on every load, that it really holds all three kinds of
 * wear, that a scratch crossing an edge carries on into the next tile, and
 * that panes do not all start in the same corner of it.
 */
import { describe, expect, it } from "vitest";
import { DIRT, DIRT_SIZE, dirtOffset } from "@/lib/dirt";

const svg = decodeURIComponent(DIRT.slice("data:image/svg+xml,".length));

describe("the picture of dirt", () => {
  it("is one large tile holding smudges, dust and scratches", () => {
    expect(svg).toContain(`width='${DIRT_SIZE}'`);
    expect(svg).toContain("id='smudge'");
    expect(svg).toContain("id='dust'");
    expect(svg.match(/<path /g)?.length).toBeGreaterThan(50);
  });

  it("draws its scratches into the eight tiles around it, so no seam shows", () => {
    expect(svg.match(/<use href='#s'/g)).toHaveLength(8);
  });
});

describe("where a pane starts in it", () => {
  it("is the same for the same widget every time", () => {
    expect(dirtOffset("f4d9029d3536")).toEqual(dirtOffset("f4d9029d3536"));
  });

  it("is somewhere inside the tile", () => {
    for (const id of ["a", "9010a2503f0c", "43dd617c482e", ""]) {
      const { x, y } = dirtOffset(id);
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThan(DIRT_SIZE);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThan(DIRT_SIZE);
    }
  });

  it("differs between widgets, so no two wear the same corner", () => {
    const ids = [
      "bbfa1b080cd0",
      "3ec143d00d15",
      "f4d9029d3536",
      "9010a2503f0c",
    ];
    const starts = new Set(ids.map((id) => JSON.stringify(dirtOffset(id))));
    expect(starts.size).toBe(ids.length);
  });
});
