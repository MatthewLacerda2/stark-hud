/**
 * YouTube's own player, and saying in English why it refused a video.
 *
 * A YouTube video has no URL a `<video>` element can take, and there is
 * deliberately no API key on this board to ask for one. What YouTube does offer
 * is the IFrame Player API: a page of theirs in an iframe, plus a small object
 * we can call play and pause on. That object is what makes a video a track like
 * any other — the transport verbs reach it, and a video that ends says so.
 *
 * The script comes from YouTube and needs no key. It is loaded once for the
 * whole board rather than per widget, because it installs a single global
 * callback and a second copy would take the first one's place.
 */
import type { Playback } from "@/lib/schemas/board";

/** The slice of the IFrame API this board actually uses. */
export interface YouTubePlayer {
  playVideo(): void;
  pauseVideo(): void;
  mute(): void;
  unMute(): void;
  loadVideoById(options: { videoId: string; startSeconds?: number }): void;
  cueVideoById(options: { videoId: string; startSeconds?: number }): void;
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  getCurrentTime(): number;
  destroy(): void;
}

/** What YouTube hands a handler: the player itself, and a number. */
export interface YouTubeEvent {
  target: YouTubePlayer;
  data: number;
}

export interface YouTubePlayerOptions {
  videoId: string;
  playerVars?: Record<string, number>;
  events?: {
    onReady?: (event: YouTubeEvent) => void;
    onStateChange?: (event: YouTubeEvent) => void;
    onError?: (event: YouTubeEvent) => void;
  };
}

export interface YouTubeApi {
  new (host: HTMLElement, options: YouTubePlayerOptions): YouTubePlayer;
}

declare global {
  interface Window {
    YT?: { Player: YouTubeApi };
    onYouTubeIframeAPIReady?: () => void;
  }
}

const SCRIPT = "https://www.youtube.com/iframe_api";

let loading: Promise<YouTubeApi> | null = null;

/**
 * The player constructor, once YouTube's script has installed it.
 *
 * Resolves straight away when it is already there, which is both the second
 * widget on the board and the way a test hands this a stub: jsdom has no
 * YouTube, so what it puts on `window.YT` is what gets used.
 */
export function youtubePlayerApi(): Promise<YouTubeApi> {
  const ready = window.YT?.Player;
  if (ready) return Promise.resolve(ready);
  loading ??= new Promise<YouTubeApi>((resolve) => {
    // The script calls this by name when it has finished installing itself.
    window.onYouTubeIframeAPIReady = () => resolve(window.YT!.Player);
    const tag = document.createElement("script");
    tag.src = SCRIPT;
    document.head.appendChild(tag);
  });
  return loading;
}

/**
 * What a state number from the player means to this board, or nothing.
 *
 * Buffering, cued and unstarted are deliberately nothing: they are the player
 * talking about itself between tracks, and reporting them would have the widget
 * announce a pause it was never asked for.
 */
export function playbackState(code: number): Playback["state"] | null {
  if (code === 0) return "ended";
  if (code === 1) return "playing";
  if (code === 2) return "paused";
  return null;
}

/**
 * Why YouTube would not play something, as a sentence rather than a number.
 *
 * This is the case the whole playback report exists for. A video whose owner
 * has switched off embedding plays nowhere but youtube.com, and the player says
 * so only as `101` or `150` — which, left alone, reaches whoever is driving the
 * board as silence. Written in English, not translated, for the same reason a
 * codec failure is: it goes to the session, not to the room.
 */
export function whyYouTubeRefused(code: number): string {
  if (code === 2) return "that is not a YouTube video id";
  if (code === 5) return "YouTube's player cannot play this video";
  if (code === 100) return "no such video: it was removed, or made private";
  if (code === 101 || code === 150) {
    return "the owner does not allow this video to be played outside YouTube";
  }
  return `YouTube refused it and would only say ${code}`;
}
