/** Typed wrappers for the board endpoints. Pages call these, never `fetch`. */

import { request } from "@/lib/api/client";
import type { BoardStatus, Item, Payload } from "@/lib/schemas/board";

export interface ItemCreate {
  payload: Payload;
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

export function createItem(body: ItemCreate): Promise<Item> {
  return request<Item>("/board/items", { method: "POST", body });
}

export function updateItem(id: string, body: ItemUpdate): Promise<Item> {
  return request<Item>(`/board/items/${id}`, { method: "PATCH", body });
}

export function removeItem(id: string): Promise<void> {
  return request<void>(`/board/items/${id}`, { method: "DELETE" });
}

export function clearBoard(): Promise<{ removed: number }> {
  return request<{ removed: number }>("/board/items", { method: "DELETE" });
}
