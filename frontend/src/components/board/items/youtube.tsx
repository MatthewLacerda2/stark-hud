import { useCallback, useEffect, useRef } from "react";
import type { Playback } from "@/lib/schemas/board";
import {
  playbackState,
  whyYouTubeRefused,
  youtubePlayerApi,
  type YouTubePlayer,
} from "@/lib/youtube";

/**
 * One YouTube video inside the media widget, played by YouTube's own player.
 *
 * This is a track, not a second widget. It takes the same state the `<video>`
 * beside it takes — which video, playing or not, muted or not — and it reports
 * back the same way, so a video that ends moves the queue on exactly as a file
 * that ends does. Nothing here is clickable, because the television has nothing
 * to click with.
 *
 * The player is built once and then told to load each next video, rather than
 * being rebuilt: rebuilding tears the iframe out of the page, which on the TV is
 * a black rectangle between tracks.
 */
export function YouTubeTrack({
  video,
  playing,
  muted,
  startSeconds,
  say,
  keep,
  name,
  className,
}: {
  video: string;
  playing: boolean;
  muted: boolean;
  /** Where this widget had got to before it was moved between layers. */
  startSeconds: number;
  say: (state: Playback["state"], error?: string) => void;
  /** Hand back the position on the way out, so maximising does not restart it. */
  keep: (seconds: number) => void;
  /** The real title, once YouTube says what it is. An id reads badly on a TV. */
  name: (title: string) => void;
  className?: string;
}) {
  const host = useRef<HTMLDivElement>(null);
  const player = useRef<YouTubePlayer | null>(null);
  // Which video the player is actually showing, which is not what the board says
  // until we have told it. Kept outside React because the player is.
  const shown = useRef(video);
  const from = useRef(startSeconds);
  // Whether it was meant to be playing when the player was built. Reloading the
  // TV on a paused widget must not blurt the video out before sync catches it.
  const began = useRef(playing);

  /** Bring the player in line with what the board says, whatever changed. */
  const sync = useCallback(() => {
    const built = player.current;
    if (!built) return;
    if (shown.current !== video) {
      shown.current = video;
      // Cue rather than load when it is not meant to be playing: loading starts
      // it, and pausing it again a moment later is a blip on the TV and a
      // spurious event on its way back to the server.
      const asked = { videoId: video, startSeconds: 0 };
      if (playing) built.loadVideoById(asked);
      else built.cueVideoById(asked);
    }
    if (muted) built.mute();
    else built.unMute();
    if (playing) built.playVideo();
    else built.pauseVideo();
  }, [video, playing, muted]);

  // Everything the player calls, read through a ref. The player outlives every
  // render, so a handler captured when it was built would report the track the
  // widget was on then rather than the one it is on now.
  const latest = useRef({ say, keep, name, sync });
  useEffect(() => {
    latest.current = { say, keep, name, sync };
  });

  useEffect(() => {
    let live = true;
    void youtubePlayerApi().then((Player) => {
      if (!live || !host.current) return;
      player.current = new Player(host.current, {
        videoId: shown.current,
        // No chrome and no related videos: nobody can press any of it, and a
        // grid of other people's thumbnails is not what this widget is for.
        playerVars: {
          autoplay: began.current ? 1 : 0,
          controls: 0,
          rel: 0,
          playsinline: 1,
          start: Math.floor(from.current),
        },
        events: {
          onReady: (event) => {
            latest.current.sync();
            const found = event.target.getVideoData().title;
            if (found) latest.current.name(found);
          },
          onStateChange: (event) => {
            const state = playbackState(event.data);
            if (state) latest.current.say(state);
          },
          onError: (event) =>
            latest.current.say("failed", whyYouTubeRefused(event.data)),
        },
      });
    });
    return () => {
      live = false;
      const built = player.current;
      if (!built) return;
      latest.current.keep(built.getCurrentTime());
      built.destroy();
      player.current = null;
    };
    // Built once. Every later change reaches it through sync, below.
  }, []);

  useEffect(sync, [sync]);

  // Two divs on purpose: YouTube replaces the inner one with its iframe, so it
  // has to be a node React is not going to look for again.
  return (
    <div className={className}>
      <div ref={host} className="size-full" />
    </div>
  );
}
