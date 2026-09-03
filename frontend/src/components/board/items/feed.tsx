import { useTranslation } from "react-i18next";
import type { FeedPayload } from "@/lib/schemas/board";
import { EntryRow } from "@/components/board/entry-row";
import { Icon } from "@/components/board/icon";
import { useClock } from "@/hooks/use-clock";

/**
 * Things that happened somewhere else, newest first.
 *
 * The same line as the inbox on purpose — one rhythm for "a thing happened" on
 * this screen — but the contents are replaced whole on every refresh rather
 * than accumulating, because whoever polls them is the authority on the list.
 *
 * Overflow is clipped rather than scrolled: nobody can scroll this screen, and
 * the newest are at the top.
 */
export function Feed({ id, payload }: { id: string; payload: FeedPayload }) {
  const { t } = useTranslation();
  // So "now" turns into a clock time when its minute passes.
  useClock();
  const empty = payload.empty ?? t("board.emptyList");

  return (
    <div className="flex size-full flex-col gap-1 overflow-hidden rounded-xl widget-surface widget-edge p-5 widget-text">
      {payload.title ? (
        <h3 className="flex shrink-0 items-center gap-2 text-node font-semibold tracking-tight">
          <Icon name={payload.icon} src={`/api/v1/media/${id}/icon`} />
          {payload.title}
        </h3>
      ) : null}
      {payload.entries.length > 0 ? (
        <ul className="min-h-0 flex-1 overflow-hidden">
          {payload.entries.map((entry, i) => (
            <EntryRow
              key={`${entry.source}-${entry.title}-${i}`}
              source={entry.source}
              at={entry.at}
              title={entry.title}
            />
          ))}
        </ul>
      ) : (
        <p className="text-node-sm opacity-60 italic">{empty}</p>
      )}
    </div>
  );
}
