import { useTranslation } from "react-i18next";
import type { FeedEntry, FeedPayload } from "@/lib/schemas/board";
import { NamedIcon } from "@/components/board/named-icon";
import { useClock } from "@/hooks/use-clock";
import { when } from "@/lib/when";

function Row({ entry }: { entry: FeedEntry }) {
  const { t } = useTranslation();
  return (
    <li className="py-2 text-node-sm">
      <div className="min-w-0">
        <div className="flex items-baseline justify-between gap-2 opacity-60">
          <span className="truncate">{entry.source ?? "—"}</span>
          {entry.at ? (
            <span className="shrink-0">
              {when(entry.at, t("inbox.justNow"))}
            </span>
          ) : null}
        </div>
        <p className="line-clamp-2 font-semibold">{entry.title}</p>
      </div>
    </li>
  );
}

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
export function Feed({ payload }: { payload: FeedPayload }) {
  const { t } = useTranslation();
  // So "now" turns into a clock time when its minute passes.
  useClock();
  const empty = payload.empty ?? t("board.emptyList");

  return (
    <div className="flex size-full flex-col gap-1 overflow-hidden rounded-xl widget-surface p-5 widget-text">
      {payload.title ? (
        <h3 className="flex shrink-0 items-center gap-2 text-node font-semibold tracking-tight">
          {payload.icon ? <NamedIcon name={payload.icon} /> : null}
          {payload.title}
        </h3>
      ) : null}
      {payload.entries.length > 0 ? (
        <ul className="min-h-0 flex-1 divide-y divide-current/10 overflow-hidden">
          {payload.entries.map((entry, i) => (
            <Row key={`${entry.source}-${entry.title}-${i}`} entry={entry} />
          ))}
        </ul>
      ) : (
        <p className="text-node-sm opacity-60 italic">{empty}</p>
      )}
    </div>
  );
}
