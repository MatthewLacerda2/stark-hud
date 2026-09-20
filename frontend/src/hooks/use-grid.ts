import { useQuery } from "@tanstack/react-query";
import { boardStatus } from "@/lib/api/board";
import type { BoardStatus } from "@/lib/schemas/board";

/** How many columns and rows the board has, and nothing else about it. */
export type Grid = Pick<BoardStatus, "cols" | "rows">;

/** Longest a retry waits, the same ceiling the socket's backoff has. */
const RETRY_MAX_MS = 10_000;

/**
 * The grid the board is drawn on, or nothing until the server has said.
 *
 * Every coordinate on this board is a fraction of the grid — a widget at x=20
 * is 20/32 of the way across — so the grid is the one number the page cannot
 * work out for itself and cannot guess at. It used to guess: 12 by 8, the
 * template's grid, kept as a fallback while `/board/status` was in flight. That
 * is not a coarser version of 32 by 18, it is a different board, and for as
 * long as it stood every widget was drawn in the wrong place at the wrong size
 * and then jumped when the real numbers landed.
 *
 * Worse than the jump: `use-entrance.ts` decides which way a widget flew in
 * once, on its first render, and a corridor measured against 12 columns for a
 * widget sitting at column 20 comes out negative — so the board picked the east
 * edge and then flew the widget in from the west. That is what looked strange.
 *
 * So there is no fallback here. `null` means the page does not know yet, and a
 * board that does not know its grid draws no widgets at all: one blank frame
 * costs a round trip on the LAN, and a wrong frame costs the first impression
 * the television makes when somebody turns it on.
 *
 * The retry is why not knowing is safe. Nobody is standing at the TV to reload
 * it, so this asks until it is answered rather than giving up after three
 * goes and leaving the screen empty for the evening.
 */
export function useGrid(): Grid | null {
  const status = useQuery({
    queryKey: ["board", "status"],
    queryFn: boardStatus,
    retry: true,
    retryDelay: (attempt) => Math.min(500 * 2 ** attempt, RETRY_MAX_MS),
  });
  return status.data ?? null;
}
