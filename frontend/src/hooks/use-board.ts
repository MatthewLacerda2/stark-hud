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
  page: number;
  /**
   * Which widgets have been told work is coming, counted rather than flagged:
   * a widget woken again while it is already awake gets a new number, which is
   * how the acknowledgement knows to hold for another spell instead of ending
   * on the first one's timer.
   *
   * Nothing here is board state — it is what somebody said they were about to
   * do, and a fresh connection knows none of it. That is why a snapshot starts
   * it empty.
   */
  wakes: Record<string, number>;
}

const EMPTY: BoardState = {
  items: [],
  background: null,
  notifications: [],
  page: 0,
  wakes: {},
};

/** The same wakes without the one for `id`. */
function settled(wakes: Record<string, number>, id: string) {
  if (!(id in wakes)) return wakes;
  const rest = { ...wakes };
  delete rest[id];
  return rest;
}

export function reduceBoard(
  state: BoardState,
  message: BoardEvent,
): BoardState {
  switch (message.event) {
    case "board.snapshot":
      return {
        items: message.data.items,
        background: message.data.background,
        notifications: message.data.notifications,
        page: message.data.page,
        wakes: {},
      };
    case "board.cleared":
      // The background is not an item; clearing the board leaves it alone.
      return { ...state, items: [], wakes: {} };
    case "board.page":
      return { ...state, page: message.data.page };
    case "background.changed":
      return { ...state, background: message.data };
    case "item.created":
      return {
        ...state,
        items: [...state.items, message.data],
        wakes: settled(state.wakes, message.data.id),
      };
    case "item.updated":
      // The answer landed, so the widget stops waiting for it. Dropping the
      // wake here rather than letting it time out is what makes the arrival
      // and the acknowledgement one movement instead of two.
      return {
        ...state,
        items: state.items.map((i) =>
          i.id === message.data.id ? message.data : i,
        ),
        wakes: settled(state.wakes, message.data.id),
      };
    case "item.waking":
      return {
        ...state,
        wakes: {
          ...state.wakes,
          [message.data.id]: (state.wakes[message.data.id] ?? 0) + 1,
        },
      };
    case "item.removed":
      return {
        ...state,
        items: state.items.filter((i) => i.id !== message.data.id),
        wakes: settled(state.wakes, message.data.id),
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
          reduceBoard(current, JSON.parse(event.data as string)),
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
