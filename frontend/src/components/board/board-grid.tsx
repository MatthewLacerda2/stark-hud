import { useCallback, useMemo, useRef, useState } from "react";
import GridLayout, {
  noCompactor,
  type Layout,
  type LayoutItem,
} from "react-grid-layout";
import type { Item, Notification } from "@/lib/schemas/board";
import { updateItem } from "@/lib/api/board";
import { ItemView } from "@/components/board/item-view";
import { WidgetControls } from "@/components/board/widget-controls";
import { useContainerSize } from "@/hooks/use-container-size";
import { drawn, maximisedIn } from "@/lib/maximised";

const MARGIN = 8;
const PADDING = 8;
// Long enough to move the pointer from the widget to the controls without them
// vanishing on the way.
const CONTROLS_LINGER_MS = 3000;

/* A widget's background starts invisible, whatever its kind. The board sits on
   a video and most widgets read better straight on top of it; the ones that
   need a panel get one from the opacity slider, one widget at a time. */
const DEFAULT_ALPHA = 0;

/** The widget's background: what its kind implies. `item.color` is for its text. */
function colourOf(item: Item): string | undefined {
  // A widget told what it is made of wins. A note's own colour still works,
  // because a sticky note that had one before this existed should keep it.
  if (item.background) return item.background;
  if (item.payload.kind === "note" && item.payload.color)
    return item.payload.color;
  return undefined;
}
// Sides resize one axis, corners resize both.
const HANDLES = ["n", "s", "e", "w", "ne", "nw", "se", "sw"] as const;

// No compaction, and no shoving either. `noCompactor` alone still displaces
// whatever a drag lands on, and with a fixed number of rows the displaced
// widget is pushed off the bottom of a board that cannot scroll — gone until
// someone reloads the page. Refusing the move instead is also what the server
// does with an overlapping placement, so the two now agree.
const NO_SHOVING = { ...noCompactor, preventCollision: true };

/** The CSS variables that say what one widget is made of. */
function widgetVars(item: Item, alpha: number): React.CSSProperties {
  return {
    "--widget-alpha": alpha,
    "--widget-colour": colourOf(item),
    "--widget-text": item.color ?? undefined,
    "--widget-scale": item.scale ?? 1,
  } as React.CSSProperties;
}

/**
 * The board, as a fixed grid that can be rearranged with a mouse.
 *
 * The server still owns placement: a drag or resize is a request, sent as a
 * PATCH, and the authoritative position comes back over the socket like any
 * other change. If the server refuses — the slot is taken, or it would fall off
 * the grid — nothing arrives, `items` never changes, and the widget snaps back.
 *
 * Compaction is off. The server places things deliberately, and a grid that
 * pulls everything upwards would fight it.
 *
 * While a widget has the whole board the grid keeps every slot and draws almost
 * nothing into them — see `drawn`. The layout is untouched, so giving the room
 * back is one render and the board comes back exactly where it was.
 */
export function BoardGrid({
  items,
  notifications,
  cols,
  rows,
}: {
  items: Item[];
  notifications: Notification[];
  cols: number;
  rows: number;
}) {
  const { ref, width, height } = useContainerSize();
  const maximised = maximisedIn(items);
  const [hovered, setHovered] = useState<string | null>(null);
  const [preview, setPreview] = useState<Record<string, number>>({});
  const linger = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const show = useCallback((id: string) => {
    clearTimeout(linger.current);
    setHovered(id);
  }, []);

  const hideSoon = useCallback(() => {
    clearTimeout(linger.current);
    linger.current = setTimeout(() => setHovered(null), CONTROLS_LINGER_MS);
  }, []);

  const alphaOf = useCallback(
    (item: Item) => preview[item.id] ?? item.opacity ?? DEFAULT_ALPHA,
    [preview],
  );

  const commitAlpha = useCallback((id: string, value: number) => {
    void updateItem(id, { opacity: value }).catch(() => {});
  }, []);

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
      // leaves `items` as it was, which snaps the widget home.
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
    <div ref={ref} className="relative size-full">
      {width > 0 && height > 0 ? (
        <GridLayout
          width={width}
          layout={layout}
          compactor={NO_SHOVING}
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
            <div
              key={item.id}
              className="@container relative min-h-0 min-w-0"
              style={widgetVars(item, alphaOf(item))}
              onMouseEnter={() => show(item.id)}
              onMouseLeave={hideSoon}
            >
              {drawn(item, maximised) ? (
                <ItemView item={item} notifications={notifications} />
              ) : null}
              {hovered === item.id ? (
                <WidgetControls
                  alpha={alphaOf(item)}
                  onPreview={(value) =>
                    setPreview((current) => ({ ...current, [item.id]: value }))
                  }
                  onCommit={(value) => commitAlpha(item.id, value)}
                />
              ) : null}
            </div>
          ))}
        </GridLayout>
      ) : null}

      {/* No padding, and a ground of its own.

          This layer used to carry the same 8px the grid puts around every
          widget, which is right for a widget among widgets and wrong for the
          only thing on the screen: a 1920x1080 film was being fitted into
          1904x1064, so it letterboxed itself to 1892x1064 and left 14px of the
          background video down each side and 8px along the top and bottom. The
          padding is the grid's, not the picture's, and here there is no grid.

          The ground is opaque because a film that is not 16:9 legitimately has
          bars, and the background behind this layer is a wallpaper video that
          has been paused — so without it the bars would be a frozen still of
          something else rather than black. */}
      {maximised ? (
        <div
          className="@container absolute inset-0 z-30 bg-background"
          style={widgetVars(maximised, alphaOf(maximised))}
        >
          <ItemView
            // It is the whole board now, so that is the size it is told it has:
            // what a widget draws depends on how many cells it was given.
            item={{ ...maximised, w: cols, h: rows }}
            notifications={notifications}
          />
        </div>
      ) : null}
    </div>
  );
}
