import type { NotePayload } from "@/lib/schemas/board";
import { ScrollingText } from "@/components/board/scrolling-text";

/**
 * A sticky note.
 *
 * Dark ground by convention: this board is a TV in a dim room, and a pale tile
 * is a lamp pointed at whoever is watching. `color` still overrides it, but a
 * light value is a deliberate choice, not the default.
 *
 * Kept more opaque than a chart on purpose. A chart is legible through its own
 * marks; prose has to be readable, and text over moving video is not.
 *
 * Text is sized in container units, so the same note reads correctly in a 2x1
 * cell and in a 6x4 one.
 */
export function Note({ payload }: { payload: NotePayload }) {
  return (
    <div
      className="flex size-full flex-col justify-center rounded-xl tile-surface p-5 text-node text-card-foreground shadow-lg backdrop-blur-sm"
      style={payload.color ? { backgroundColor: payload.color } : undefined}
    >
      <ScrollingText text={payload.text} />
    </div>
  );
}
