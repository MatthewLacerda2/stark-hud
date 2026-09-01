/**
 * Board types, mirroring `backend/schemas/board.py`.
 *
 * Payloads are a discriminated union on `kind`, so a component can switch on
 * one field and TypeScript narrows the rest.
 */

export type ChartKind = "line" | "bar" | "pie" | "area" | "radial";
export type NotifyLevel = "info" | "success" | "warn" | "error";

export interface NotePayload {
  kind: "note";
  text: string;
  color: string | null;
}

export interface TextPayload {
  kind: "text";
  text: string;
  size: "sm" | "md" | "lg" | "xl";
}

export interface ListPayload {
  kind: "list";
  title: string | null;
  items: string[];
  empty: string | null;
  /** Heading and entries can be coloured apart; null takes the widget's colour. */
  title_color: string | null;
  item_color: string | null;
}

export interface BoxPayload {
  kind: "box";
  label: string | null;
  fill: string | null;
  stroke: string | null;
}

export interface ImagePayload {
  kind: "image";
  path: string;
  alt: string | null;
}

export interface VideoPayload {
  kind: "video";
  path: string;
  autoplay: boolean;
  loop: boolean;
  muted: boolean;
}

export interface ChartPayload {
  kind: "chart";
  chart: ChartKind;
  data: Record<string, string | number>[];
  x_key: string;
  series: string[];
  title: string | null;
  /** A ceiling for the value axis; a radial always has one. */
  max: number | null;
  unit: string | null;
  /** One CSS colour per series, cycled. Empty means the default palette. */
  colors: string[];
}

export interface InboxPayload {
  kind: "inbox";
  title: string | null;
}

/** One line in a feed: a notification's shape, minus level and icon. */
export interface FeedEntry {
  title: string;
  source: string | null;
  at: string | null;
}

export interface FeedPayload {
  kind: "feed";
  title: string | null;
  /** A name from the notification icon set, drawn beside the heading. */
  icon: string | null;
  entries: FeedEntry[];
  empty: string | null;
}

/** Nothing is written to a clock: the browser already knows the time. */
export interface ClockPayload {
  kind: "clock";
}

/** One notification. They live in an inbox, not on the grid. */
export interface Notification {
  id: string;
  title: string;
  body: string | null;
  /** A name from the icon set, or an absolute path to a local image. */
  icon: string | null;
  level: NotifyLevel;
  source: string | null;
  /** Colours for this entry. Null means white, whatever the widget is. */
  title_color: string | null;
  body_color: string | null;
  created_at: string;
}

export type Payload =
  | NotePayload
  | TextPayload
  | ListPayload
  | BoxPayload
  | ImagePayload
  | VideoPayload
  | ChartPayload
  | InboxPayload
  | ClockPayload
  | FeedPayload;

export type ItemKind = Payload["kind"];

export interface Item {
  id: string;
  /** A name given by whoever writes this panel repeatedly, so it can find it. */
  key: string | null;
  /** How solid this widget's background is, 0 to 1. Null means its kind's default. */
  opacity: number | null;
  /** The widget's background colour. Null means its kind's default. */
  color: string | null;
  /** Multiplies the text sizes inside the widget. Null means 1. */
  scale: number | null;
  payload: Payload;
  x: number;
  y: number;
  w: number;
  h: number;
  parent_id: string | null;
  pinned: boolean;
  created_at: string;
}

export interface Placement {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** A looping, always-silent video behind the grid. */
export interface Background {
  path: string;
  blur: boolean;
}

export interface BoardSnapshot {
  items: Item[];
  background: Background | null;
  notifications: Notification[];
}

export interface BoardStatus {
  cols: number;
  rows: number;
  cells_total: number;
  cells_used: number;
  cells_free: number;
  item_count: number;
  largest_free_rect: Placement | null;
}

/** Events pushed over the board socket. */
export type BoardEvent =
  | { event: "board.snapshot"; data: BoardSnapshot }
  | { event: "background.changed"; data: Background | null }
  | { event: "board.cleared"; data: { removed: number } }
  | { event: "item.created"; data: Item }
  | { event: "item.updated"; data: Item }
  | { event: "item.removed"; data: { id: string } }
  | { event: "notification.created"; data: Notification }
  | { event: "notification.removed"; data: { id: string } }
  | { event: "notifications.cleared"; data: { removed: number } };
