import type { NotePayload } from "@/lib/schemas/board";
import { ScrollingText } from "@/components/board/scrolling-text";

/**
 * A sticky note: text straight on the board, like every widget that is not a
 * picture. Its text colour and scale are applied by the grid, so one place
 * decides how every widget looks.
 *
 * Text is sized in container units, so the same note reads correctly in a 2x1
 * cell and in a 6x4 one.
 */
export function Note({ payload }: { payload: NotePayload }) {
  return (
    <div className="flex size-full flex-col justify-center rounded-xl widget-edge p-[4cqmin] text-node widget-text">
      <ScrollingText text={payload.text} />
    </div>
  );
}
