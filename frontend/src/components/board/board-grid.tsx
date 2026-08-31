import type { Item } from "@/lib/schemas/board";
import { ItemView } from "@/components/board/item-view";

/**
 * The board, as a fixed CSS grid.
 *
 * The server owns placement — it already refused anything that did not fit — so
 * this only translates cells into `grid-column` / `grid-row`. Keeping one source
 * of truth for layout is why there is no drag-and-drop grid library here.
 */
export function BoardGrid({
  items,
  cols,
  rows,
}: {
  items: Item[];
  cols: number;
  rows: number;
}) {
  return (
    <div
      className="grid size-full gap-3 p-3"
      style={{
        gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
        gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
      }}
    >
      {items.map((item) => (
        <div
          key={item.id}
          // @container: item text sizes in `cqi` units, so a note in a 2x1
          // cell and the same note in a 6x4 cell both read correctly.
          className="@container min-h-0 min-w-0 animate-[fade-in_200ms_ease-out]"
          style={{
            gridColumn: `${item.x + 1} / span ${item.w}`,
            gridRow: `${item.y + 1} / span ${item.h}`,
          }}
        >
          <ItemView item={item} />
        </div>
      ))}
    </div>
  );
}
