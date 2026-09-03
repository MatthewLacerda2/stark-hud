import { useCallback, useRef, useState } from "react";
import type { Item, Notification } from "@/lib/schemas/board";
import { updateItem } from "@/lib/api/board";
import { ItemView } from "@/components/board/item-view";
import { WidgetControls } from "@/components/board/widget-controls";
import { WidgetWake } from "@/components/board/widget-wake";
import { Vhs } from "@/components/board/vhs";
import { useContainerSize } from "@/hooks/use-container-size";
import { useLeaving } from "@/hooks/use-leaving";
import { useWidgetDrag } from "@/hooks/use-widget-drag";
import { EDGES, type Rect } from "@/lib/drag";
import { held } from "@/lib/groups";
import { drawn, maximisedIn } from "@/lib/maximised";
import { cn } from "@/lib/utils";
import { holographic, type Tape } from "@/lib/vhs";
import { lit, type Bloom } from "@/lib/bloom";

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
/** Just the four numbers a gesture is allowed to touch.
 *
 * An `Item` is a `Rect` and a great deal else, and handing the whole thing to
 * the gesture meant the whole thing came back out of it: a drag PATCHed the
 * payload, the key and the parent alongside the coordinates. Harmless while
 * nothing else was changing, and a way to quietly undo a panel refresh that
 * landed mid-drag — the widget would be written back with the contents it had
 * when the pointer went down.
 */
function rectOf(item: Item): Rect {
  return { x: item.x, y: item.y, w: item.w, h: item.h };
}

/** Where a widget sits on the board, as a share of it.
 *
 * Percentages rather than pixels because that is what the coordinates already
 * are: a fraction of a board 32 columns wide. Nothing has to be measured for a
 * widget to be drawn in the right place, so the board is correct on its first
 * paint rather than after a ResizeObserver has reported. The gutter between
 * widgets is padding inside each one, which keeps this arithmetic exact.
 */
function frame(rect: Rect, cols: number, rows: number): React.CSSProperties {
  return {
    left: `${(rect.x / cols) * 100}%`,
    top: `${(rect.y / rows) * 100}%`,
    width: `${(rect.w / cols) * 100}%`,
    height: `${(rect.h / rows) * 100}%`,
  };
}

/**
 * The class that puts the look on what this widget draws, if it should have it.
 *
 * Pictures get neither, for the reason they never got the tape: a film is
 * somebody else's picture, and a filter over moving video re-runs every frame.
 */
function looked(item: Item, tape: Tape, bloom: Bloom): string | undefined {
  if (!holographic(item.payload.kind)) return undefined;
  const taped = tape.grain > 0 || tape.scanlines > 0;
  const glowing = lit(bloom);
  if (taped && glowing) return "bloom-holo";
  if (glowing) return "bloom-lit";
  if (taped) return "vhs-holo";
  return undefined;
}

/** The CSS variables that say what one widget is made of. */
function widgetVars(item: Item, alpha: number): React.CSSProperties {
  return {
    "--widget-alpha": alpha,
    "--widget-colour": colourOf(item),
    "--widget-text": item.color ?? undefined,
    // Transparent rather than absent, so the line costs nothing when nobody
    // asked for one and the rule below needs no condition to express.
    "--widget-border": item.border ?? "transparent",
    "--widget-scale": item.scale ?? 1,
  } as React.CSSProperties;
}

/**
 * The board: widgets placed where they were put, and rearrangeable with a mouse.
 *
 * There is no grid library here and no grid. A widget is absolutely positioned
 * as a share of the board, which is what its coordinates already were, and a
 * pointer handler moves and resizes it — see `lib/drag.ts` for the arithmetic
 * and `use-widget-drag.ts` for the gesture.
 *
 * The server still owns placement: a drag or resize is a request, sent as a
 * PATCH, and the authoritative position comes back over the socket like any
 * other change. If the server refuses — something is already there, or it would
 * fall off the board — nothing arrives, `items` never changes, and the widget
 * snaps back to where it was.
 *
 * While a widget has the whole board the others stay exactly where they are and
 * draw almost nothing — see `drawn`. Nothing about the layout changes, so giving
 * the room back is one render and the board comes back as it was.
 *
 * `wakes` counts how often each widget has been told work is coming. It is not
 * part of what a widget is, so it rides beside the items rather than on them:
 * nothing about the board has changed at the point one of these arrives.
 *
 * `tape` is the look, and it arrives here rather than being drawn over the
 * whole page because it belongs to the panes and not to the room behind them.
 */
export function BoardGrid({
  items,
  everything,
  notifications,
  wakes,
  tape,
  bloom,
  cols,
  rows,
}: {
  /** The widgets on the board: what `onBoard` left after the folded ones. */
  items: Item[];
  /** Everything that exists, folded widgets included — what a group draws from. */
  everything: Item[];
  notifications: Notification[];
  wakes: Record<string, number>;
  tape: Tape;
  /** How much light the widgets spill. One setting for the whole board. */
  bloom: Bloom;
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

  // The socket delivers the result, so nothing here waits on the response for
  // anything but knowing when to stop holding the widget under the pointer.
  const persist = useCallback(
    (id: string, rect: Rect) => updateItem(id, rect).catch(() => {}),
    [],
  );
  const { grab, placed, holding } = useWidgetDrag(
    { cols, rows, width, height },
    persist,
  );
  // Removal is the one change with nothing left to animate by the time the
  // board hears about it, so what has just gone is held for as long as it takes
  // to be seen going.
  const { drawn: onScreen, leaving, forget } = useLeaving(items);

  return (
    <div className="relative size-full">
      {/* The coordinate space, inset by half a gutter so a widget against the
          wall sits as far from it as two widgets sit from each other. Percentages
          are measured against this box, and it is this box that is measured, so
          a pointer travelling one cell moves a widget exactly one cell. */}
      <div ref={ref} className="absolute inset-1">
        {onScreen.map((item) => {
          const rect = placed(item.id, rectOf(item));
          const going = leaving(item.id);
          return (
            <div
              key={item.id}
              // Half the gutter on every side. Doing it here rather than in the
              // arithmetic above is what lets a widget's position be a plain
              // fraction of the board with nothing subtracted from it.
              className={cn(
                "absolute p-1",
                holding === item.id ? "cursor-grabbing" : "cursor-grab",
                // Not while a pointer is holding it: a widget easing towards
                // where the hand already is lags behind the hand.
                holding === item.id ? undefined : "widget-settle",
                going ? "widget-leaving" : "widget-arriving",
              )}
              style={frame(rect, cols, rows)}
              onPointerDown={(event) =>
                grab(event, item.id, rectOf(item), "move")
              }
              onAnimationEnd={going ? () => forget(item.id) : undefined}
            >
              <div
                className="@container relative size-full min-h-0 min-w-0"
                style={widgetVars(item, alphaOf(item))}
                onMouseEnter={() => show(item.id)}
                onMouseLeave={hideSoon}
              >
                {drawn(item, maximised) ? (
                  <>
                    <div className={cn("size-full", looked(item, tape, bloom))}>
                      <ItemView
                        item={item}
                        notifications={notifications}
                        holds={held(item, everything)}
                      />
                    </div>
                    <Vhs tape={tape} />
                    <WidgetWake nonce={wakes[item.id] ?? 0} />
                  </>
                ) : null}
                {hovered === item.id ? (
                  <WidgetControls
                    alpha={alphaOf(item)}
                    onPreview={(value) =>
                      setPreview((current) => ({
                        ...current,
                        [item.id]: value,
                      }))
                    }
                    onCommit={(value) => commitAlpha(item.id, value)}
                  />
                ) : null}
                {/* Invisible until the pointer is over the widget, and never on
                    the television, which has no pointer at all. */}
                {EDGES.map((edge) => (
                  <div
                    key={edge}
                    className={`widget-grip widget-grip-${edge}`}
                    onPointerDown={(event) =>
                      grab(event, item.id, rectOf(item), edge)
                    }
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

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
          <div className={cn("size-full", looked(maximised, tape, bloom))}>
            <ItemView
              // It is the whole board now, so that is the size it is told it
              // has: what a widget draws depends on how many cells it was given.
              item={{ ...maximised, w: cols, h: rows }}
              notifications={notifications}
            />
          </div>
          <Vhs tape={tape} />
          <WidgetWake nonce={wakes[maximised.id] ?? 0} />
        </div>
      ) : null}
    </div>
  );
}
