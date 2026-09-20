import { useTranslation } from "react-i18next";
import type { FeedPayload } from "@/lib/schemas/board";
import { EntryRow } from "@/components/board/entry-row";
import { WidgetHeading } from "@/components/board/widget-heading";
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
    <div className="flex size-full flex-col gap-1 overflow-hidden rounded-xl widget-edge p-[4cqmin] widget-text">
      <WidgetHeading id={id} icon={payload.icon} title={payload.title} />
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
