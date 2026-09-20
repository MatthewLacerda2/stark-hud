import { cn } from "@/lib/utils";

/**
 * The space a held widget is about to take.
 *
 * ## Why this is allowed to exist
 *
 * `CLAUDE.md`, *Looks beat handling*: **"Do not add an affordance to the screen
 * to make something easier to move."** This file draws something, on purpose,
 * and the argument lives here so that the next session reads it before deleting
 * it — which would otherwise be the right instinct.
 *
 * The argument is the rule's own stated reason. The same paragraph says chrome
 * "appears on hover, where a pointer exists, and so never appears on the
 * television at all". This rectangle is drawn only while a pointer is held down
 * on a widget. The television has no mouse and nobody touches it, so it can
 * never appear there — not once, not for a frame. It is the hover exemption,
 * one gesture further in.
 *
 * It is also not an invitation to start a gesture, which is what the rule is
 * about. Nothing is drawn while nothing is being dragged; no handle, grip,
 * outline or grid appears to make a widget easier to *grab*. This is feedback
 * during a gesture already in progress.
 *
 * The board had exactly this until commit `bb526c8` took `react-grid-layout`
 * out, whose stylesheet drew `.react-grid-placeholder` in red at a fifth
 * opacity. It was never argued against; it left with the library. The owner
 * asked for it back on #168, and gave the reason the rule requires of an
 * override: *"ajuda muito."*
 *
 * ## What it shows
 *
 * One question, always the same one: **where this widget will be when the hand
 * opens.** So a drop that will be taken draws the seat it is going to, at the
 * size it will be — and the size is the half that matters, because shrink-to-fit
 * is the outcome nobody can predict by eye. A drop that will be refused draws
 * the seat it is going *back* to, which is the one it came from.
 *
 * ## The colour
 *
 * `ring`, which is the grey the resize grips are already drawn in: the board
 * already has a colour for "this is the pointer's business", and this is the
 * only other thing on the screen that is. Red is kept for the refusal, where it
 * means refused rather than meaning "here" — the board's rule about colour is
 * that red, green and blue carry meaning and decoration burns the signal, and
 * the ordinary case of this rectangle carries no meaning worth a hue.
 *
 * No glass, deliberately. A pane with a thickness is what a widget is, and a
 * preview that had one would read as a second widget rather than as a space.
 *
 * No motion either, which is how `prefers-reduced-motion` is answered: there is
 * nothing to turn off. It appears, it follows the hand, it goes.
 */
export function DropPreview({
  style,
  fits,
}: {
  /** The same four percentages a widget is placed with — see `frame`. */
  style: React.CSSProperties;
  /** Whether the board will take this rectangle, or the widget goes home. */
  fits: boolean;
}) {
  return (
    // Half the gutter on every side, exactly as a widget has, so the rectangle
    // is the space the widget will fill and not the cell it will sit in.
    <div className="pointer-events-none absolute p-1" style={style} aria-hidden>
      <div
        className={cn(
          "size-full drop-preview",
          fits ? "drop-preview-fits" : "drop-preview-home",
        )}
      />
    </div>
  );
}
