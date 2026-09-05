import type { CSSProperties } from "react";
import type { Ink } from "@/lib/schemas/board";

/**
 * The board's own text colour, as the variables the widgets read.
 *
 * Two variables and not more. `--color-card-foreground` is what a widget writes
 * in when it was not told a colour — see the `widget-text` utility — and
 * `--color-foreground` is what everything else on the board inherits. The muted
 * one is deliberately left alone: it is dimmer *than* the ink on purpose, and
 * dragging it along would flatten the one distinction the palette draws between
 * a reading and the label beside it.
 *
 * Nothing is returned for no ink, rather than the stylesheet's value written out
 * again. The default belongs in one place, and that place is `styles.css`: a
 * copy here would be a second answer to what white-at-65% is, and the two would
 * disagree the first time either moved.
 */
export function inkVars(ink: Ink | null): CSSProperties {
  if (!ink) return {};
  return {
    "--color-foreground": ink.color,
    "--color-card-foreground": ink.color,
  } as CSSProperties;
}
