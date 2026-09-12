import { useEffect, useRef, useState } from "react";
import { stale } from "@/lib/freshness";
import type {
  Background,
  BoardEvent,
  Ink,
  Item,
  Notification,
  Origin,
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

/**
 * How many origins the page keeps around.
 *
 * Each one draws for about two seconds and then draws nothing, so this is not a
 * limit on what is shown — the server already caps that. It is how long a spent
 * one lingers in state before the next few push it out, and a handful is enough
 * that nothing is ever dropped while it is still on screen.
 */
const ORIGINS_KEPT = 4;

interface BoardState {
  items: Item[];
  background: Background | null;
  ink: Ink | null;
  notifications: Notification[];
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
   * How many times each mesh has been told its file changed under it.
   *
   * A counter rather than a flag, and read as one: the widget folds it into the
   * key it fetches geometry by, so a second telling refetches even though the
   * widget's id and its path are both the same as they were. That is the whole
   * mechanism — there is nothing to switch off afterwards.
   *
   * Not board state, like `wakes` beside it: a page that connects after a
   * reload has just fetched the current file anyway, so a snapshot starts this
   * empty and loses nothing.
   */
  reloads: Record<string, number>;
  /**
   * Lines the board has been told to say out loud since this page connected.
   *
   * A queue rather than the latest one: two agents speaking at the same moment
   * arrive as two messages in one tick, and a single slot would drop the first.
   * Trimmed to the last few, because nothing here reads an old one twice.
   */
  spoken: Spoken[];
  /**
   * What made each of the last few widgets, in the order the calls arrived.
   *
   * Beside the items rather than on them, for the reason `wakes` is: nothing
   * about the board has changed at the point one of these turns up, and a
   * widget is not a different widget for having been asked for out loud.
   *
   * A list rather than a map keyed by id, because that is what it is: a few
   * things that were just said. An id is never reused, so the widget each one
   * belongs to is found by looking, and one whose widget has gone simply draws
   * nothing.
   */
  origins: Origin[];
}

const EMPTY: BoardState = {
  items: [],
  background: null,
  ink: null,
  notifications: [],
  wakes: {},
  reloads: {},
  spoken: [],
  origins: [],
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
        ink: message.data.ink,
        notifications: message.data.notifications,
        wakes: {},
        // Nothing to carry across a reconnect: the page is about to fetch each
        // model's geometry for the first time anyway, so it has the file as it
        // is on disk right now and has no older version to be told about.
        reloads: {},
        // A reconnect does not replay what was said while the page was away: a
        // television reading out the afternoon's announcements because someone
        // restarted the browser is worse than one that misses a line.
        spoken: [],
        // A page that has just loaded has missed every call that built the
        // board it is showing, and that is right: an origin is what somebody
        // just did, not a property of what is on screen.
        origins: [],
      };
    case "speech.spoken":
      return {
        ...state,
        spoken: [...state.spoken, message.data].slice(-SPOKEN_KEPT),
      };
    case "board.cleared":
      // The background is not an item; clearing the board leaves it alone.
      return { ...state, items: [], wakes: {}, origins: [] };
    case "board.arranged":
      // One event for a change that moved several widgets. Sent whole rather
      // than as a burst of updates so that folding a group is one render on the
      // television, instead of a fold crawling across it a widget at a time.
      return { ...state, items: message.data.items };
    case "background.changed":
      return { ...state, background: message.data };
    case "ink.changed":
      return { ...state, ink: message.data };
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
    case "mesh.reloaded":
      // Deliberately not cleared when the geometry lands, unlike a wake. A wake
      // is a promise that something is coming and is settled by its arrival;
      // this is a count of how many times the file has moved, and the number
      // only has to differ from the last one the widget saw.
      return {
        ...state,
        reloads: {
          ...state.reloads,
          [message.data.id]: (state.reloads[message.data.id] ?? 0) + 1,
        },
      };
    case "item.origin":
      // Only ever appended. Nothing here clears one when it has finished
      // playing: the popup ends itself on its own animation, and an entry that
      // has stopped drawing costs a few characters until the next few push it
      // out. There is no moment in this reducer that knows when two seconds
      // are up, and inventing one would mean a clock in a pure function.
      return {
        ...state,
        origins: [...state.origins, message.data].slice(-ORIGINS_KEPT),
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
    let first = true;

    const open = () => {
      socket = new WebSocket(WS_URL);

      socket.onopen = () => {
        retryRef.current = RETRY_MIN_MS;
        setConnected(true);
        // A backend restart is what a deploy looks like from here, so coming
        // back is the moment to ask whether this page is still running the code
        // the server is serving. Not on the first connection of a page's life:
        // it has just loaded whatever it was given and cannot be behind.
        if (!first) void stale().then((old) => old && location.reload());
        first = false;
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
