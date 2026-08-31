import type { NotePayload } from "@/lib/schemas/board";

/**
 * A sticky note.
 *
 * Dark ground by convention: this board is a TV in a dim room, and a pale tile
 * is a lamp pointed at whoever is watching. `color` still overrides it, but a
 * light value is a deliberate choice, not the default.
 *
 * Text is sized in container units, so the same note reads correctly in a 2x1
 * cell and in a 6x4 one.
 */
export function Note({ payload }: { payload: NotePayload }) {
  return (
    <div
      className="flex size-full flex-col justify-center rounded-xl bg-card/80 p-5 text-node text-card-foreground shadow-lg backdrop-blur-sm"
      style={payload.color ? { backgroundColor: payload.color } : undefined}
    >
      <p className="wrap-break-word whitespace-pre-wrap">{payload.text}</p>
    </div>
  );
}
