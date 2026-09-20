/** Typed wrappers for the board endpoints. Pages call these, never `fetch`. */

import { request } from "@/lib/api/client";
import type { BoardStatus, Item, Payload, Playback } from "@/lib/schemas/board";

/** What the page tells the server a media widget is doing. */
export interface PlaybackReport {
  state: Playback["state"];
  track?: number;
  error?: string;
  /** How far into the track it has got. Sent every few seconds, never per frame. */
  seconds?: number;
}

/**
 * What a PATCH may write, mirroring `ItemUpdate` in `backend/schemas/board.py`.
 *
 * No `parent_id` and no `page`: which group a widget is in and which page it is
 * on are trades the server makes whole, never fields a PATCH writes.
 *
 * Written out rather than derived from a create shape. There used to be an
 * `ItemCreate` here that this was an `Omit<Partial<…>>` of, and because nothing
 * ever called the create it drifted from the backend unnoticed — no `key`, no
 * `border`. A shape nothing sends is a shape nothing checks.
 */
export interface ItemUpdate {
  payload?: Payload;
  key?: string;
  /** A note only sessions read; never drawn. See `Item.description`. */
  description?: string;
  color?: string;
  border?: string;
  scale?: number;
  /** Takes this widget's glass off, or puts it back. See `Item.flat`. */
  flat?: boolean;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
}

export function boardStatus(): Promise<BoardStatus> {
  return request<BoardStatus>("/board/status");
}

export function updateItem(id: string, body: ItemUpdate): Promise<Item> {
  return request<Item>(`/board/items/${id}`, { method: "PATCH", body });
}

/**
 * Say what a media widget is doing. The only call that runs this direction.
 *
 * A finished track is also how the queue moves on: the server decides what
 * follows it, because loop-or-stop is one rule and it lives in one place.
 */
export function reportPlayback(
  id: string,
  body: PlaybackReport,
): Promise<Item> {
  return request<Item>(`/board/items/${id}/playback`, {
    method: "POST",
    body,
  });
}
