/**
 * What the URL is allowed to say about the look.
 *
 * This dial exists because the person judging it is across a room from the
 * screen, so the two things that matter are that a bare address shows the look
 * at all, and that `?vhs=0` really means off — including for a part that was
 * named on its own and would otherwise argue with the master.
 */
import { describe, expect, it } from "vitest";
import { NO_TAPE, tapeFrom, tapeVars } from "@/lib/vhs";

describe("tapeFrom", () => {
  it("shows the whole look when nothing is asked for", () => {
    expect(tapeFrom("")).toEqual({
      scanlines: 1,
      grain: 1,
      vignette: 1,
      fringe: 1,
      sweep: 1,
    });
  });

  it("scales every part by the master", () => {
    expect(tapeFrom("?vhs=0.5")).toEqual({
      scanlines: 0.5,
      grain: 0.5,
      vignette: 0.5,
      fringe: 0.5,
      sweep: 0.5,
    });
  });

  it("turns the board back into a board at zero", () => {
    expect(tapeFrom("?vhs=0")).toEqual(NO_TAPE);
  });

  it("lets one part be looked at on its own", () => {
    const tape = tapeFrom("?grain=0&fringe=0.25");
    expect(tape.grain).toBe(0);
    expect(tape.fringe).toBe(0.25);
    expect(tape.scanlines).toBe(1);
  });

  it("keeps the master's veto over a named part", () => {
    expect(tapeFrom("?vhs=0&grain=1").grain).toBe(0);
  });

  it("ignores a number that is not one, rather than drawing it", () => {
    expect(tapeFrom("?vhs=lots")).toEqual(tapeFrom(""));
    expect(tapeFrom("?grain=4").grain).toBe(1);
    expect(tapeFrom("?grain=-2").grain).toBe(0);
  });
});

describe("tapeVars", () => {
  it("names every part, so a stale variable cannot linger in the stylesheet", () => {
    expect(tapeVars(NO_TAPE)).toEqual({
      "--vhs-scanlines": 0,
      "--vhs-grain": 0,
      "--vhs-vignette": 0,
      "--vhs-fringe": 0,
      "--vhs-sweep": 0,
    });
  });
});
