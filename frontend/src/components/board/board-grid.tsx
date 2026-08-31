import { useCallback, useMemo } from "react";
import GridLayout, {
  noCompactor,
  type Layout,
  type LayoutItem,
} from "react-grid-layout";
import type { Item } from "@/lib/schemas/board";
import { updateItem } from "@/lib/api/board";
import { ItemView } from "@/components/board/item-view";
import { useContainerSize } from "@/hooks/use-container-size";

const MARGIN = 8;
const PADDING = 8;
// Sides resize one axis, corners resize both.
const HANDLES = ["n", "s", "e", "w", "ne", "nw", "se", "sw"] as const;

/**
 * The board, as a fixed grid that can be rearranged with a mouse.
 *
 * The server still owns placement: a drag or resize is a request, sent as a
 * PATCH, and the authoritative position comes back over the socket like any
 * other change. If the server refuses — the slot is taken, or it would fall off
 * the grid — nothing arrives, `items` never changes, and the tile snaps back.
 *
 * Compaction is off. The server places things deliberately, and a grid that
 * pulls everything upwards would fight it.
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
  const { ref, width, height } = useContainerSize();

  const rowHeight = useMemo(() => {
    const usable = height - PADDING * 2 - MARGIN * (rows - 1);
    return Math.max(1, usable / rows);
  }, [height, rows]);

  const layout: Layout = useMemo(
    () =>
      items.map((item) => ({
        i: item.id,
        x: item.x,
        y: item.y,
        w: item.w,
        h: item.h,
        maxW: cols,
        maxH: rows,
      })),
    [items, cols, rows],
  );

  const persist = useCallback(
    (_layout: Layout, _old: LayoutItem | null, next: LayoutItem | null) => {
      if (!next) return;
      const before = items.find((i) => i.id === next.i);
      if (!before) return;
      if (
        before.x === next.x &&
        before.y === next.y &&
        before.w === next.w &&
        before.h === next.h
      ) {
        return;
      }
      // Fire and forget: the socket delivers the result, and a rejection simply
      // leaves `items` as it was, which snaps the tile home.
      void updateItem(next.i, {
        x: next.x,
        y: next.y,
        w: next.w,
        h: next.h,
      }).catch(() => {});
    },
    [items],
  );

  return (
    <div ref={ref} className="size-full">
      {width > 0 && height > 0 ? (
        <GridLayout
          width={width}
          layout={layout}
          compactor={noCompactor}
          gridConfig={{
            cols,
            maxRows: rows,
            rowHeight,
            margin: [MARGIN, MARGIN],
            containerPadding: [PADDING, PADDING],
          }}
          dragConfig={{ enabled: true, bounded: true, cancel: ".no-drag" }}
          resizeConfig={{ enabled: true, handles: HANDLES }}
          onDragStop={persist}
          onResizeStop={persist}
        >
          {items.map((item) => (
            <div key={item.id} className="@container min-h-0 min-w-0">
              <ItemView item={item} />
            </div>
          ))}
        </GridLayout>
      ) : null}
    </div>
  );
}
