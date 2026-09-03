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
  wakes: {},
  spoken: [],
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
    // The inbox is newest first, both in the snapshot and in what the widget
    // draws, so an arrival goes on the front rather than the end.
    case "notification.created":
      return {
        ...state,
        notifications: [message.data, ...state.notifications],
      };
    case "notification.removed":
      return {
        ...state,
        notifications: state.notifications.filter(
          (n) => n.id !== message.data.id,
        ),
      };
    case "notifications.cleared":
      return { ...state, notifications: [] };
    default: {
      // `message` is `never` here only while every arm of BoardEvent is handled
      // above, so an event added to the union and forgotten here stops
      // compiling. It is what the three notification arms needed and did not
      // have: they fell through this default for as long as they existed, and
      // an inbox that only filled on page load looked exactly like an empty one.
      //
      // The state is still returned unchanged at runtime. A backend a version
      // ahead of this page should leave the television showing what it has,
      // not break on a word it does not know yet.
      const unhandled: never = message;
      void unhandled;
      return state;
    }
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
