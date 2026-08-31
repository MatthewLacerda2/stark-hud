import { useEffect, useRef, useState } from "react";
import type { BoardEvent, Item } from "@/lib/schemas/board";

/**
 * Live board state, fed entirely by the socket.
 *
 * The server sends a full snapshot on connect and a delta per change, so there
 * is no polling and no separate initial fetch. A dropped connection retries
 * with a backoff: the TV is unattended, so the page has to heal itself.
 */

const WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) ??
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;

const RETRY_MIN_MS = 500;
const RETRY_MAX_MS = 10_000;

function reduce(items: Item[], message: BoardEvent): Item[] {
  switch (message.event) {
    case "board.snapshot":
      return message.data;
    case "board.cleared":
      return [];
    case "item.created":
      return [...items, message.data];
    case "item.updated":
      return items.map((i) => (i.id === message.data.id ? message.data : i));
    case "item.removed":
      return items.filter((i) => i.id !== message.data.id);
    default:
      return items;
  }
}

export function useBoard(): { items: Item[]; connected: boolean } {
  const [items, setItems] = useState<Item[]>([]);
  const [connected, setConnected] = useState(false);
  const retryRef = useRef(RETRY_MIN_MS);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let closed = false;

    const open = () => {
      socket = new WebSocket(WS_URL);

      socket.onopen = () => {
        retryRef.current = RETRY_MIN_MS;
        setConnected(true);
      };

      socket.onmessage = (event) => {
        setItems((current) =>
          reduce(current, JSON.parse(event.data as string)),
        );
      };

      socket.onclose = () => {
        setConnected(false);
        if (closed) return;
        timer = setTimeout(open, retryRef.current);
        retryRef.current = Math.min(retryRef.current * 2, RETRY_MAX_MS);
      };
    };

    open();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, []);

  return { items, connected };
}
