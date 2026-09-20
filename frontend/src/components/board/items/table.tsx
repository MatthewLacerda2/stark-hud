import { useTranslation } from "react-i18next";
import type { TableColumn, TablePayload } from "@/lib/schemas/board";
import { cn } from "@/lib/utils";
import { WidgetHeading } from "@/components/board/widget-heading";

/** The grid both halves are laid on, in shares rather than measured widths.
 *
 * The heading and the rows are two grids, because the heading has to stay put
 * while the rows scroll past it. Two grids only agree on where a column starts
 * if neither is sizing it from its own contents, so every column is a fraction
 * of the widget and none of them is `auto`.
 */
function template(columns: TableColumn[]): string {
  return columns.map((column) => `${column.width}fr`).join(" ");
}

/** One row of cells, or the headings, which are the same shape. */
function Row({
  columns,
  className,
  cell,
}: {
  columns: TableColumn[];
  className?: string;
  cell: (column: TableColumn) => string;
}) {
  return (
    <div
      className={cn("grid items-baseline gap-[2cqmin]", className)}
      style={{ gridTemplateColumns: template(columns) }}
    >
      {columns.map((column) => (
        <span
          key={column.key}
          className={cn(
            // Never wrap. A long name that took two lines would make one row
            // twice the height of its neighbours, and a table whose lines are
            // different heights stops reading as columns.
            "truncate",
            column.align === "right" && "text-right tabular-nums",
          )}
        >
          {cell(column)}
        </span>
      ))}
    </div>
  );
}

/**
 * Rows of text under named columns.
 *
 * The case a list cannot do: four readings per line that have to line up down
 * the screen, so the eye can run down one column and compare. A list would have
 * to pad them into one string and hope for a monospaced font, and could still
 * never put the numbers on the right where their digits align.
 *
 * Nothing here is computed. Cells are drawn exactly as they arrive, units and
 * all, because whoever measured the number knows how it should read and this
 * does not.
 *
 * It does not scroll, which is the one place this departs from the list. A list
 * scrolls because every line in it matters and nobody can scroll this screen,
 * so a line left off would simply be lost. A table's rows are in the order
 * whoever sent them chose, and a panel refreshing every few seconds that also
 * creeps up and down is a thing in the corner of the eye rather than something
 * read — so what does not fit is not drawn, and the rows that fall off the
 * bottom are the ones their own order put last. Send more rows than fit and
 * this draws the top of them.
 *
 * The headings are a size down and faded: a column heading is the least
 * important thing here — it is read once and then never again — and the rows
 * are what somebody is actually looking at.
 */
export function Table({ id, payload }: { id: string; payload: TablePayload }) {
  const { t } = useTranslation();
  const empty = payload.empty ?? t("board.emptyList");

  return (
    // Half the inset the other widgets keep. A table is columns, and its own
    // margin is width the columns do not get — on a panel this wide and this
    // short, that padding was costing a readable gap between the name and the
    // first number.
    <div className="flex size-full flex-col gap-2 rounded-xl widget-edge p-[2cqmin] widget-text">
      <WidgetHeading
        id={id}
        icon={payload.icon}
        iconColor={payload.icon_color}
        title={payload.title}
        titleColor={payload.title_color}
      />
      {payload.rows.length > 0 ? (
        <>
          <Row
            columns={payload.columns}
            className="shrink-0 text-node-sm font-semibold tracking-wide uppercase opacity-50"
            cell={(column) => column.label ?? column.key}
          />
          <div
            className="min-h-0 flex-1 overflow-hidden text-node-sm font-semibold opacity-85"
            style={payload.row_color ? { color: payload.row_color } : undefined}
          >
            {payload.rows.map((row, i) => (
              <Row
                key={`${i}-${payload.columns[0]?.key ?? ""}`}
                columns={payload.columns}
                cell={(column) => row[column.key] ?? ""}
              />
            ))}
          </div>
        </>
      ) : (
        <p className="text-node-sm font-semibold italic opacity-70">{empty}</p>
      )}
    </div>
  );
}
