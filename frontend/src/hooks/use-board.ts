import { useEffect, useRef, useState } from "react";
import type {
  Background,
  BoardEvent,
  Item,
  Notification,
} from "@/lib/schemas/board";

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

interface BoardState {
  items: Item[];
  background: Background | null;
  notifications: Notification[];
}

const EMPTY: BoardState = { items: [], background: null, notifications: [] };

function reduce(state: BoardState, message: BoardEvent): BoardState {
  switch (message.event) {
    case "board.snapshot":
      return {
        items: message.data.items,
        background: message.data.background,
        notifications: message.data.notifications,
      };
    case "board.cleared":
      // The background is not an item; clearing the board leaves it alone.
      return { ...state, items: [] };
    case "background.changed":
      return { ...state, background: message.data };
    case "item.created":
      return { ...state, items: [...state.items, message.data] };
    case "item.updated":
      return {
        ...state,
        items: state.items.map((i) =>
          i.id === message.data.id ? message.data : i,
        ),
      };
    case "item.removed":
      return {
        ...state,
        items: state.items.filter((i) => i.id !== message.data.id),
      };
    default:
      return state;
  }
}

export function useBoard(): BoardState & { connected: boolean } {
  const [state, setState] = useState<BoardState>(EMPTY);
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
        setState((current) =>
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

  return { ...state, connected };
}
