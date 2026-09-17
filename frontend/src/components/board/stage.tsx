import { useRef, type ReactNode } from "react";
import { useLean } from "@/hooks/use-lean";
import { deep, depthVars, type Depth } from "@/lib/depth";

/**
 * The space the board stands in: one camera, and the board leaning inside it.
 *
 * One perspective for the whole board rather than one per widget. A widget
 * given its own perspective turns about its own middle, and ten widgets turning
 * about ten middles is ten pictures tilting, not one thing in a room.
 *
 * Only the board is inside. The background video stays flat behind it, so the
 * panes slide over the room, and the command bar stays flat in front, because it
 * is something being typed into rather than something on the board.
 *
 * With depth off this is nothing at all — not a wrapper with no effect, but no
 * element — so `?depth=0` is the board exactly as it was before depth existed.
 */
export function Stage({
  depth,
  still,
  children,
}: {
  depth: Depth;
  /** Level and motionless: a widget has the whole screen. */
  still: boolean;
  children: ReactNode;
}) {
  const board = useRef<HTMLDivElement>(null);
  useLean(board, depth, still);

  if (!deep(depth)) return children;
  return (
    <div className="size-full depth-stage" style={depthVars(depth)}>
      <div ref={board} className="size-full depth-board">
        {children}
      </div>
    </div>
  );
}
