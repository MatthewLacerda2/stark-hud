/**
 * What a table shows, mirroring `backend/schemas/table.py`.
 *
 * Its own module because `board.ts` is at the house's 550-line ceiling.
 * `board.ts` re-exports it, so nothing has to know.
 */

import type { IconRef } from "@/lib/schemas/board";

/** Which edge of its column a cell sits against. */
export type Align = "left" | "right";

/** One column: the field it reads out of every row, and how it sits. */
export interface TableColumn {
  key: string;
  /** Null makes the key the heading. */
  label: string | null;
  align: Align;
  /** Its share of the width against the other columns' shares. */
  width: number;
}

/**
 * Rows of text under named columns.
 *
 * Every cell is already the text it should draw — the units were chosen by
 * whoever measured the number, and nothing here reformats one.
 */
export interface TablePayload {
  kind: "table";
  title: string | null;
  icon: IconRef | null;
  columns: TableColumn[];
  rows: Record<string, string>[];
  empty: string | null;
  title_color: string | null;
  icon_color: string | null;
  row_color: string | null;
}
