import type { CSSProperties } from "react";

/**
 * How much of the tape look to draw, part by part.
 *
 * A dashboard in a film is never a clean render. There is a grain over it, the
 * lines of a tube through it, and the colour separates a little at the edges of
 * the letters. None of that carries information — it is what makes information
 * look *displayed* rather than pasted on, and it is the reason a HUD in a film
 * reads as a thing in a room.
 *
 * Every part is a number from 0 to 1, where 1 is the strongest each one goes
 * before it stops being a look and starts being damage. What that means in
 * pixels lives in `styles.css`, next to the layer it belongs to: this file only
 * says how much.
 */
export type Tape = {
  /** The lines of the tube, drawn across everything. */
  scanlines: number;
  /** Moving grain. The part that reads as tape rather than as a screen. */
  grain: number;
  /** Corners going dark, the way a lens does. */
  vignette: number;
  /** Colour separating at the edges of text. */
  fringe: number;
  /** The tracking bar, crossing the picture every few seconds. */
  sweep: number;
};

/** No look at all: the board exactly as it was before any of this existed. */
export const NO_TAPE: Tape = {
  scanlines: 0,
  grain: 0,
  vignette: 0,
  fringe: 0,
  sweep: 0,
};

/** Every part at full. What `?vhs=1` — and no query string at all — means. */
const FULL: Tape = {
  scanlines: 1,
  grain: 1,
  vignette: 1,
  fringe: 1,
  sweep: 1,
};

const PARTS = Object.keys(FULL) as (keyof Tape)[];

function amount(raw: string | null, fallback: number): number {
  const value = raw === null ? fallback : Number(raw);
  return Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : fallback;
}

/**
 * Read the look out of a query string.
 *
 * `?vhs=0.4` turns the whole thing down, `?vhs=0` turns it off, and any part
 * can be named on its own — `?grain=0&fringe=0.3` — to see what that one is
 * doing. A named part is still scaled by `vhs`, so turning the master to zero
 * really does mean off.
 *
 * The URL is the dial on purpose. This is a television across the room from the
 * person judging it, and the alternative to a number they can type is a rebuild
 * for every guess.
 */
export function tapeFrom(search: string): Tape {
  const asked = new URLSearchParams(search);
  const master = amount(asked.get("vhs"), 1);
  const tape = { ...NO_TAPE };
  for (const part of PARTS) {
    tape[part] = amount(asked.get(part), FULL[part]) * master;
  }
  return tape;
}

/** The same numbers, as the variables the stylesheet reads. */
export function tapeVars(tape: Tape): CSSProperties {
  return {
    "--vhs-scanlines": tape.scanlines,
    "--vhs-grain": tape.grain,
    "--vhs-vignette": tape.vignette,
    "--vhs-fringe": tape.fringe,
    "--vhs-sweep": tape.sweep,
  } as CSSProperties;
}
