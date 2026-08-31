import type { NotePayload } from "@/lib/schemas/board";

/** A sticky note: body text on a card, sized to be read across a room. */
export function Note({ payload }: { payload: NotePayload }) {
  return (
    <div
      className="flex size-full flex-col justify-center rounded-xl bg-card p-5 text-h3 text-card-foreground shadow-lg"
      style={payload.color ? { backgroundColor: payload.color } : undefined}
    >
      <p className="wrap-break-word whitespace-pre-wrap">{payload.text}</p>
    </div>
  );
}
