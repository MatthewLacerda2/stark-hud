import type { CSSProperties } from "react";
import type { Ink } from "@/lib/schemas/board";

/**
 * The board's own text colour, as the variables the widgets actually read.
 *
 * Three, and each is a different spelling of the same colour, because the board
 * writes text through two mechanisms that reach it by different routes.
 *
 * `@theme inline` inlines a token's *value* into the utility, so `text-foreground`
 * compiles to `color: var(--foreground)` and never looks at `--color-foreground`
 * at all. That is why the underlying names are set: they are what Tailwind's own
 * utilities resolve against.
 *
 * `widget-text` is hand-written in `styles.css` as
 * `var(--widget-text, var(--color-card-foreground))`, so it reads the prefixed
 * name instead — and setting `--card-foreground` here cannot reach it. A custom
 * property's `var()` is substituted where it is *declared*, and
 * `--color-card-foreground: var(--card-foreground)` is declared on `:root`, so
 * what every widget inherits already carries the root's value whatever this
 * element says. Both spellings, or half the board ignores the ink.
 *
 * `--color-foreground` is deliberately absent. The only rule that reads it sets
 * the colour of `body`, which is outside the board, so writing it here changed
 * nothing at all.
 *
 * The muted colour is left alone on purpose: it is dimmer *than* the ink, and
 * dragging it along would flatten the distinction the palette draws between a
 * reading and the label beside it.
 *
 * Nothing is returned for no ink, rather than the stylesheet's value written out
 * again. The default belongs in one place, and that place is `styles.css`: a
 * copy here would be a second answer to what white-at-65% is, and the two would
 * disagree the first time either moved.
 */
export function inkVars(ink: Ink | null): CSSProperties {
  if (!ink) return {};
  return {
    "--foreground": ink.color,
    "--card-foreground": ink.color,
    "--color-card-foreground": ink.color,
  } as CSSProperties;
}
