import { useEffect, useRef, useState } from "react";
import type {
  Background,
  BoardEvent,
  Item,
  Notification,
  Spoken,
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

/** How many spoken lines the page remembers. Enough to outlast a burst. */
const SPOKEN_KEPT = 8;

interface BoardState {
  items: Item[];
  background: Background | null;
  notifications: Notification[];
  page: number;
  /**
   * Lines the board has been told to say out loud since this page connected.
   *
   * A queue rather than the latest one: two agents speaking at the same moment
   * arrive as two messages in one tick, and a single slot would drop the first.
   * Trimmed to the last few, because nothing here reads an old one twice.
   */
  spoken: Spoken[];
}

const EMPTY: BoardState = {
  items: [],
  background: null,
  notifications: [],
  page: 0,
  spoken: [],
};

function reduce(state: BoardState, message: BoardEvent): BoardState {
  switch (message.event) {
    case "board.snapshot":
      return {
        items: message.data.items,
        background: message.data.background,
        notifications: message.data.notifications,
        page: message.data.page,
        // A reconnect does not replay what was said while the page was away: a
        // television reading out the afternoon's announcements because someone
        // restarted the browser is worse than one that misses a line.
        spoken: [],
      };
    case "speech.spoken":
      return {
        ...state,
        spoken: [...state.spoken, message.data].slice(-SPOKEN_KEPT),
      };
    case "board.cleared":
      // The background is not an item; clearing the board leaves it alone.
      return { ...state, items: [] };
    case "board.page":
      return { ...state, page: message.data.page };
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
