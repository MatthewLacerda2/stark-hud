import { useTranslation } from "react-i18next";
import type { FeedEntry, FeedPayload } from "@/lib/schemas/board";
import { useClock } from "@/hooks/use-clock";
import { when } from "@/lib/when";

function Row({ entry }: { entry: FeedEntry }) {
  const { t } = useTranslation();
  return (
    <li className="flex gap-3 py-2 text-node-sm">
      {/* Where the inbox puts an icon. Fixed width so every title starts on the
          same column, which is what makes a list of these scannable. */}
      <span className="mt-[0.15em] w-[3.2em] shrink-0 text-center font-semibold tracking-wide tabular-nums opacity-50">
        {entry.badge ?? ""}
      </span>
      <div className="min-w-0 flex-1">
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
        <h3 className="shrink-0 text-node font-semibold tracking-tight">
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
