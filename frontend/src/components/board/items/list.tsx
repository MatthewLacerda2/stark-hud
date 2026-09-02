import { useTranslation } from "react-i18next";
import type { ListEntry, ListPayload } from "@/lib/schemas/board";
import { cn } from "@/lib/utils";
import { EntryRow } from "@/components/board/entry-row";
import { Icon } from "@/components/board/icon";
import { Scrolling } from "@/components/board/scrolling";

/** A plain line, read as the entry it is the short form of. */
function asEntry(item: string | ListEntry): ListEntry {
  return typeof item === "string"
    ? {
        title: item,
        body: null,
        icon: null,
        title_color: null,
        body_color: null,
        icon_color: null,
      }
    : item;
}

/**
 * A heading and the lines under it.
 *
 * Separate sizes and weights are the whole reason this is not a note: a title
 * that looks like its own entries is not a title. Entries sit below it a size
 * down and slightly faded — hierarchy without a second colour, so a widget told
 * to be orange is orange throughout.
 *
 * An entry is a line of text or a small thing with a title, a body and an icon.
 * Plain lines draw as running text, the way a printed list does; one rich entry
 * turns every line into a row instead, because the two rhythms in one widget
 * read as a mistake rather than as two kinds of line.
 *
 * They scroll when there are more of them than fit, because nobody can scroll
 * this screen — rows as much as text.
 *
 * Every part of it can be coloured, and the rule is one sentence: an entry's
 * own colour wins, then the widget-wide one — `title_color` for the heading and
 * the icon beside it, `item_color` for anything inside an entry — then the
 * widget's colour, which is the case that needs no thought.
 */
export function List({ id, payload }: { id: string; payload: ListPayload }) {
  const { t } = useTranslation();
  const empty = payload.empty ?? t("board.emptyList");
  const rich = payload.items.some((item) => typeof item !== "string");

  return (
    <div className="flex size-full flex-col gap-2 rounded-xl widget-surface p-5 widget-text">
      {payload.title || payload.icon ? (
        <h3
          className={cn(
            "shrink-0 text-node font-semibold tracking-tight",
            // Only an icon needs the heading to become a row; without one it is
            // the heading it always was.
            payload.icon && "flex items-center gap-2",
          )}
          style={
            payload.title_color ? { color: payload.title_color } : undefined
          }
        >
          {payload.icon ? (
            <Icon
              name={payload.icon}
              src={`/api/v1/media/${id}/icon`}
              color={payload.icon_color ?? undefined}
            />
          ) : null}
          {payload.title}
        </h3>
      ) : null}
      {payload.items.length > 0 ? (
        <Scrolling
          content={payload.items}
          className="flex-1 text-node-sm font-semibold opacity-85"
          color={payload.item_color ?? undefined}
        >
          {rich ? (
            <ul>
              {payload.items.map((item, i) => {
                const entry = asEntry(item);
                return (
                  <EntryRow
                    key={`${i}-${entry.title}`}
                    icon={
                      entry.icon ? (
                        <Icon
                          name={entry.icon}
                          src={`/api/v1/media/${id}/icon/${i}`}
                          color={entry.icon_color ?? undefined}
                        />
                      ) : undefined
                    }
                    title={entry.title}
                    titleColor={entry.title_color ?? undefined}
                    body={entry.body}
                    bodyColor={entry.body_color ?? undefined}
                  />
                );
              })}
            </ul>
          ) : (
            <p className="wrap-break-word whitespace-pre-wrap">
              {payload.items.join("\n")}
            </p>
          )}
        </Scrolling>
      ) : (
        <p className="text-node-sm font-semibold italic opacity-70">{empty}</p>
      )}
    </div>
  );
}
