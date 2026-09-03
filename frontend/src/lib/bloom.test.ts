/**
 * The dials the board is judged by.
 *
 * This look is settled by somebody standing in front of a television typing a
 * number, so the numbers have to survive whatever they type — including the
 * nonsense typed on the way to the number they meant.
 */
import { describe, expect, it } from "vitest";
import { bloomFrom, lit } from "@/lib/bloom";

describe("how much light the widgets spill", () => {
  it("is none at all when nobody asked", () => {
    expect(lit(bloomFrom(""))).toBe(false);
    expect(lit(bloomFrom("?vhs=1"))).toBe(false);
  });

  it("comes on together when only the master is given", () => {
    const bloom = bloomFrom("?bloom=1");
    expect(bloom.spread).toBeGreaterThan(0);
    expect(bloom.glow).toBeGreaterThan(0);
    expect(lit(bloom)).toBe(true);
  });

  it("separates how far the light carries from how much of it there is", () => {
    // The whole point of two dials: tight and bright, and wide and faint, are
    // different looks rather than two amounts of one look.
    const tight = bloomFrom("?bloom=1&spread=0.15&glow=1");
    const wide = bloomFrom("?bloom=1&spread=1&glow=0.3");
    expect(tight.spread).toBeLessThan(wide.spread);
    expect(tight.glow).toBeGreaterThan(wide.glow);
  });

  it("is off when there is no light, however far it would have carried", () => {
    expect(lit(bloomFrom("?bloom=1&glow=0"))).toBe(false);
    expect(lit(bloomFrom("?bloom=1&spread=0"))).toBe(false);
  });

  it("scales its parts by the master, so zero really is off", () => {
    const bloom = bloomFrom("?bloom=0&spread=1&glow=1");
    expect(bloom.spread).toBe(0);
    expect(bloom.glow).toBe(0);
    expect(lit(bloom)).toBe(false);
  });

  it("leaves the cutoff alone, because a line is not an amount", () => {
    // Scaling it would drag the line towards zero and make MORE of the board
    // bloom as you asked for less of it.
    expect(bloomFrom("?bloom=0.2").cutoff).toBe(bloomFrom("?bloom=1").cutoff);
    expect(bloomFrom("?bloom=1&cutoff=0.3").cutoff).toBe(0.3);
  });

  it("stays a look rather than becoming damage", () => {
    expect(bloomFrom("?bloom=1&spread=7").spread).toBe(1);
    expect(bloomFrom("?bloom=1&glow=-2").glow).toBe(0);
  });

  it("lets the light past one, because intensity is a multiplier", () => {
    // Overdriving this is how a thing reads as bright rather than as pale, and
    // it is the one part where a ceiling of one would be the wrong answer.
    expect(bloomFrom("?bloom=1&glow=2").glow).toBe(2);
    // Still bounded, so a typo cannot white out the room.
    expect(bloomFrom("?bloom=1&glow=99").glow).toBe(4);
  });

  it("ignores what is not a number, instead of drawing NaN", () => {
    expect(lit(bloomFrom("?bloom=lots"))).toBe(false);
    expect(bloomFrom("?bloom=1&spread=wide").spread).toBeGreaterThan(0);
  });

  it("does not answer to the tape's dial, being a different thing", () => {
    // `?vhs=0` is a board with no tape on it. It is not a board with no light.
    expect(lit(bloomFrom("?vhs=0&bloom=0.6"))).toBe(true);
  });
});
