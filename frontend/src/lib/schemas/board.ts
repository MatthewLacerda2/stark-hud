/**
 * Board types, mirroring `backend/schemas/board.py`.
 *
 * Payloads are a discriminated union on `kind`, so a component can switch on
 * one field and TypeScript narrows the rest.
 */

export type ChartKind = "line" | "bar" | "pie" | "area" | "radial";
/** Which axes a cartesian chart draws. A pie and a radial have neither. */
export type ChartAxes = "both" | "x" | "y" | "none";
export type NotifyLevel = "info" | "success" | "warn" | "error";

/**
 * An icon is one of three things, told apart by how it starts: a name from the
 * closed set, an absolute path to a picture on this machine, or SVG markup —
 * which the backend rebuilt from an allowlist before it was ever stored.
 */
export type IconRef = string;

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

/** One line of a list, when a plain string is not enough for it. */
export interface ListEntry {
  title: string;
  body: string | null;
  icon: IconRef | null;
  /** This line's own colours; each beats the widget's `item_color`. */
  title_color: string | null;
  body_color: string | null;
  icon_color: string | null;
}

export interface ListPayload {
  kind: "list";
  title: string | null;
  /** Drawn beside the heading. */
  icon: IconRef | null;
  /** A plain line, or one with a body and an icon of its own. Mixing is allowed. */
  items: (string | ListEntry)[];
  empty: string | null;
  /**
   * The widget-wide colours: the heading, the icon beside it, and every entry
   * that named none of its own. Null takes the widget's colour.
   */
  title_color: string | null;
  icon_color: string | null;
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

/**
 * One entry in a media widget's queue: a file on the machine running the board,
 * or a video on YouTube. Exactly one of the two is set.
 *
 * A local track is served by the widget's id and this track's place in the
 * queue, so the path never leaves the server. A YouTube track is served by
 * YouTube, so nothing about it is fetched from here at all.
 */
export interface MediaTrack {
  path: string | null;
  /** An eleven-character YouTube video id, whatever shape of link it arrived as. */
  youtube: string | null;
  title: string | null;
  /**
   * Who is playing and what record it came off, read from the file's own tags
   * on the server. Either may be missing, and a track that has neither says
   * only its title rather than a row of labels reading "Unknown".
   */
  artist: string | null;
  album: string | null;
  /**
   * A short digest of the file this track names, to hang on the end of the URL
   * that fetches it. A track is addressed by the widget's id and its place in
   * the queue, so without this a replaced queue is the same URL over different
   * bytes, and the browser goes on playing what it already had.
   */
  stamp: string | null;
  kind: "audio" | "video" | "youtube";
}

/**
 * A queue of files and YouTube videos that plays itself through.
 *
 * The transport is state, not a stream of commands: the server holds what is
 * true and the page renders it, so a reload finds the widget where it left it.
 * What the page then managed to do about it is `Item.playback`, not here.
 */
export interface MediaPayload {
  kind: "media";
  tracks: MediaTrack[];
  /** Which track the widget is on. */
  index: number;
  /** Whether it should be playing. Not whether it is — that is the report. */
  playing: boolean;
  /** What happens when the queue runs out: start again, or stop. */
  loop: boolean;
  muted: boolean;
  /** Takes the whole board and gives it back; the grid slot is kept either way. */
  maximised: boolean;
  /** Whether YouTube draws its captions. Off unless somebody asked for them. */
  captions: boolean;
  /**
   * How far into the current track the widget is. Kept here, on the server,
   * because it has to outlive the page: a reload and a restart both come back
   * to where a four-hour film was rather than to its beginning.
   */
  seconds: number;
  /** An album's name for a queue whose files carry no tags of their own. */
  title: string | null;
}

/** What the page last told the server this widget was doing. */
export interface Playback {
  state: "idle" | "playing" | "paused" | "ended" | "failed";
  track: number | null;
  title: string | null;
  error: string | null;
  at: string;
}

/**
 * A value a mark changes colour above.
 *
 * `at` is in the units of the plotted value, so a gauge drawing a percentage is
 * crossed at 77, not at the twelve gigabytes that percentage stands for.
 */
export interface ChartThreshold {
  at: number;
  color: string;
}

export interface ChartPayload {
  kind: "chart";
  chart: ChartKind;
  data: Record<string, string | number>[];
  x_key: string;
  series: string[];
  /** A radial draws this in the middle of its ring; every other chart, in its corner. */
  title: string | null;
  /** Drawn beside a gauge's title. Nothing else draws it yet. */
  icon: IconRef | null;
  /** A ceiling for the value axis; a radial always has one. */
  max: number | null;
  /** What the numbers are counted in. Nothing draws it since the gauge stopped. */
  unit: string | null;
  /** Which axes to draw. Ignored by pie and radial, which have none. */
  axes: ChartAxes;
  /** A gauge's ring behind the value. Null takes the default. Gauges only. */
  unfilled: string | null;
  /** One CSS colour per series, cycled. Empty means the default palette. */
  colors: string[];
  /**
   * Values above which a mark turns, so colour is a signal and not decoration.
   * The highest one a value clears wins; under all of them the mark keeps the
   * colour it had. Bar and radial only — a pie and a line colour by series
   * already, so they ignore this. Empty is the default.
   */
  thresholds: ChartThreshold[];
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
  /** Drawn beside the heading. */
  icon: IconRef | null;
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
  icon: IconRef | null;
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
  | MediaPayload
  | ChartPayload
  | InboxPayload
  | ClockPayload
  | FeedPayload;

export type ItemKind = Payload["kind"];

export interface Item {
  id: string;
  /** A name given by whoever writes this panel repeatedly, so it can find it. */
  key: string | null;
  /**
   * A note left by whatever drives the board, for whatever drives it next.
   * Nothing renders it — it is deliberately invisible on the TV. It is mirrored
   * here so that a drag, which PATCHes the item, cannot drop it on the way back.
   */
  description: string | null;
  /** How solid this widget's background is, 0 to 1. Null means its kind's default. */
  opacity: number | null;
  background: string | null;
  /** The widget's background colour. Null means its kind's default. */
  color: string | null;
  /** Multiplies the text sizes inside the widget. Null means 1. */
  scale: number | null;
  payload: Payload;
  /**
   * What the browser says this widget is actually doing. Only a media widget
   * ever has one, and only the browser can know it: a file may be gone, or in a
   * codec it will not decode. It is kept beside `description` rather than in the
   * payload so that rewriting the widget does not erase it.
   */
  playback: Playback | null;
  /** Which screen this widget is on. The board shows exactly one at a time. */
  page: number;
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
  /** The page being shown, the same for every client. */
  page: number;
}

export interface BoardStatus {
  cols: number;
  rows: number;
  /** Occupancy is per page; these describe the one being shown. */
  page: number;
  pages: number;
  cells_total: number;
  cells_used: number;
  cells_free: number;
  item_count: number;
  largest_free_rect: Placement | null;
}

/**
 * A line the board has been told to say out loud, already synthesised.
 *
 * `url` is where the audio is, addressed by id: the backend has no speakers, so
 * the page is the only thing here that can actually say it.
 */
export interface Spoken {
  id: string;
  text: string;
  url: string;
  created_at: string;
}

/** Events pushed over the board socket. */
export type BoardEvent =
  | { event: "board.snapshot"; data: BoardSnapshot }
  | { event: "background.changed"; data: Background | null }
  | { event: "board.cleared"; data: { removed: number } }
  | { event: "board.page"; data: { page: number } }
  | { event: "item.created"; data: Item }
  | { event: "item.updated"; data: Item }
  /* Work is coming for this widget; nothing about it has changed yet. Sent by
     whoever is about to write to it, before they go and work out what to write. */
  | { event: "item.waking"; data: { id: string } }
  | { event: "item.removed"; data: { id: string } }
  | { event: "notification.created"; data: Notification }
  | { event: "notification.removed"; data: { id: string } }
  | { event: "notifications.cleared"; data: { removed: number } }
  | { event: "speech.spoken"; data: Spoken };
