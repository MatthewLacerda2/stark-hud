import { useTranslation } from "react-i18next";
import type { ListPayload } from "@/lib/schemas/board";
import { ScrollingText } from "@/components/board/scrolling-text";

/**
 * A heading and the lines under it.
 *
 * Separate sizes and weights are the whole reason this is not a note: a title
 * that looks like its own entries is not a title. Entries sit below it a size
 * down and slightly faded — hierarchy without a second colour, so a tile told
 * to be orange is orange throughout.
 *
 * They scroll when there are more of them than fit, because nobody can scroll
 * this screen.
 *
 * The heading and the entries can be coloured apart. Left alone they both take
 * the tile's colour, which is the case that needs no thought.
 */
export function List({ payload }: { payload: ListPayload }) {
  const { t } = useTranslation();
  const empty = payload.empty ?? t("board.emptyList");

  return (
    <div className="flex size-full flex-col gap-2 rounded-xl tile-surface p-5 tile-text">
      {payload.title ? (
        <h3
          className="shrink-0 text-node font-semibold tracking-tight"
          style={
            payload.title_color ? { color: payload.title_color } : undefined
          }
        >
          {payload.title}
        </h3>
      ) : null}
      {payload.items.length > 0 ? (
        <ScrollingText
          text={payload.items.join("\n")}
          className="flex-1 text-node-sm font-semibold opacity-85"
          color={payload.item_color ?? undefined}
        />
      ) : (
        <p className="text-node-sm font-semibold italic opacity-70">{empty}</p>
      )}
    </div>
  );
}
