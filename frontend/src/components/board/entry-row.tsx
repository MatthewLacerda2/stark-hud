import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { when } from "@/lib/when";

/**
 * One line of "here is a thing": an icon, where it came from and when, the text.
 *
 * The inbox, the feed and a list of rich entries all draw this same line, and
 * for a while each drew its own copy of it. They stay three different kinds —
 * what a line means and where it comes from is each widget's own business —
 * this is only the shape they agreed on, so one rhythm reads across the board.
 *
 * Leave out `source` and `at` and the line above the title is not drawn at all,
 * which is the case of a list: nothing there came from anywhere in particular.
 *
 * A title gets two lines when it is all there is and one when a body follows
 * it, so whatever the line is mostly made of gets the room.
 */
export function EntryRow({
  icon,
  source,
  at,
  title,
  titleColor,
  body,
  bodyColor,
}: {
  icon?: ReactNode;
  source?: string | null;
  at?: string | null;
  title: string;
  /** Left out, the text takes whatever colour the widget is. */
  titleColor?: string;
  body?: string | null;
  bodyColor?: string;
}) {
  const { t } = useTranslation();
  const meta = source !== undefined || at !== undefined;

  return (
    <li className="flex gap-3 py-2 text-node-sm">
      {icon ? <span className="mt-[0.15em]">{icon}</span> : null}
      <div className="min-w-0 flex-1">
        {meta ? (
          <div className="flex items-baseline justify-between gap-2 opacity-60">
            <span className="truncate">{source ?? "—"}</span>
            {at ? (
              <span className="shrink-0">{when(at, t("inbox.justNow"))}</span>
            ) : null}
          </div>
        ) : null}
        <p
          className={`font-semibold ${body ? "truncate" : "line-clamp-2"}`}
          style={titleColor ? { color: titleColor } : undefined}
        >
          {title}
        </p>
        {body ? (
          <p
            className="line-clamp-2 opacity-75"
            style={bodyColor ? { color: bodyColor } : undefined}
          >
            {body}
          </p>
        ) : null}
      </div>
    </li>
  );
}
