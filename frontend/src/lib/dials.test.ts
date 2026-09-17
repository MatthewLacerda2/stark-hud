/**
 * The look's numbers, as the menu reads, turns and keeps them.
 *
 * The part worth pinning is who wins. A dial typed into the address has always
 * meant what it says, and a dial chosen from the menu is what this browser asked
 * for — get the order wrong and one of them silently stops working.
 */
import { describe, expect, it } from "vitest";
import { BLOOM_DIALS, bloomFrom } from "@/lib/bloom";
import { DEPTH_DIALS, depthFrom } from "@/lib/depth";
import {
  dialValue,
  dialsOf,
  lookFrom,
  withDial,
  withoutDials,
} from "@/lib/dials";
import { TAPE_DIALS, tapeFrom } from "@/lib/vhs";

const GROUPS = [TAPE_DIALS, BLOOM_DIALS, DEPTH_DIALS];
const DIALS = dialsOf(GROUPS);
const byName = (param: string) => DIALS.find((dial) => dial.param === param)!;

describe("what a dial reads", () => {
  it("is the look's own default when nothing says otherwise", () => {
    // Each look's default has to agree with what that look actually draws with
    // no query string, or the menu opens showing a number that is not on screen.
    expect(dialValue("", byName("depth"))).toBe(0.5);
    expect(dialValue("", byName("bloom"))).toBe(0);
    expect(dialValue("", byName("vhs"))).toBe(1);
    expect(dialValue("", byName("glow"))).toBe(bloomFrom("?bloom=1").glow);
    expect(dialValue("", byName("tilt")) * 0.5).toBe(depthFrom("").tilt);
    expect(dialValue("", byName("dirt"))).toBe(tapeFrom("").dirt);
  });

  it("holds to the dial's ceiling, which is not always one", () => {
    expect(dialValue("?glow=9", byName("glow"))).toBe(4);
    expect(dialValue("?tilt=9", byName("tilt"))).toBe(1);
    expect(dialValue("?tilt=nope", byName("tilt"))).toBe(0.2);
  });
});

describe("turning a dial", () => {
  it("writes the number into the query string", () => {
    expect(withDial("", byName("bloom"), 0.6)).toBe("?bloom=0.6");
  });

  it("leaves the query string when turned back to its default", () => {
    expect(withDial("?bloom=0.6&vhs=0.3", byName("bloom"), 0)).toBe("?vhs=0.3");
    expect(withDial("?bloom=0.6", byName("bloom"), 0)).toBe("");
  });

  it("resets only the dials it is given", () => {
    expect(withoutDials("?vhs=0&x=1", DIALS)).toBe("?x=1");
  });
});

describe("what this browser kept, and the address over it", () => {
  it("uses what was kept when the address says nothing", () => {
    expect(lookFrom("?bloom=0.6", "", DIALS)).toBe("?bloom=0.6");
  });

  it("lets the address win a dial both of them name", () => {
    expect(lookFrom("?bloom=0.6&vhs=0.2", "?bloom=1", DIALS)).toBe(
      "?vhs=0.2&bloom=1",
    );
  });

  it("takes nothing from either side that is not a dial", () => {
    expect(lookFrom("?stale=1", "?utm=tv", DIALS)).toBe("");
  });
});
