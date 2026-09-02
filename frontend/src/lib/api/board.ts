/** Typed wrappers for the board endpoints. Pages call these, never `fetch`. */

import { request } from "@/lib/api/client";
import type {
  Background,
  BoardStatus,
  Item,
  Payload,
  Playback,
} from "@/lib/schemas/board";

/** What the page tells the server a media widget is doing. */
export interface PlaybackReport {
  state: Playback["state"];
  track?: number;
  error?: string;
  /** How far into the track it has got. Sent every few seconds, never per frame. */
  seconds?: number;
}

export interface ItemCreate {
  payload: Payload;
  /** A note only sessions read; never drawn. See `Item.description`. */
  description?: string;
  page?: number;
  opacity?: number;
  background?: string;
  color?: string;
  scale?: number;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  parent_id?: string | null;
  pinned?: boolean;
}

export type ItemUpdate = Partial<ItemCreate>;

export function listItems(): Promise<Item[]> {
  return request<Item[]>("/board/items");
}

export function boardStatus(): Promise<BoardStatus> {
  return request<BoardStatus>("/board/status");
}

/** Turn the board to a page, for every client at once. */
export function showPage(page: number): Promise<{ page: number }> {
  return request<{ page: number }>("/board/page", {
    method: "PUT",
    body: { page },
  });
}

export function createItem(body: ItemCreate): Promise<Item> {
  return request<Item>("/board/items", { method: "POST", body });
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

export function removeItem(id: string): Promise<void> {
  return request<void>(`/board/items/${id}`, { method: "DELETE" });
}

export function clearBoard(): Promise<{ removed: number }> {
  return request<{ removed: number }>("/board/items", { method: "DELETE" });
}

export function getBackground(): Promise<Background | null> {
  return request<Background | null>("/board/background");
}

export function setBackground(body: Background): Promise<Background> {
  return request<Background>("/board/background", { method: "PUT", body });
}

export function clearBackground(): Promise<void> {
  return request<void>("/board/background", { method: "DELETE" });
}
