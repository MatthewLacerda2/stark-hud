import { useCallback, useEffect, useRef } from "react";
import type { Playback } from "@/lib/schemas/board";
import { APART_SECONDS, ASK_SECONDS } from "@/lib/playback";
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
  captions,
  seconds,
  startSeconds,
  say,
  keep,
  className,
}: {
  video: string;
  playing: boolean;
  muted: boolean;
  /** Whether to ask YouTube for its subtitles. Off unless somebody asked. */
  captions: boolean;
  /** Where the board says this widget is, which is also where to go on a seek. */
  seconds: number;
  /** Where this widget had got to before it was moved between layers. */
  startSeconds: number;
  say: (state: Playback["state"], error?: string) => void;
  /** Hand back the position on the way out, so maximising does not restart it. */
  keep: (seconds: number) => void;
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
  // Captions are a player parameter, and player parameters are read once, when
  // the player is built. So this is a setting chosen with the queue rather than
  // a transport verb: turning it on reaches the next player, not this one.
  const subtitles = useRef(captions);

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
    // Somewhere to go only when it is somewhere this player is not: the board is
    // always a tick behind, and obeying that would jog the video every ten
    // seconds. Nothing else can reach into a video — the television has no
    // pointer to drag with — so a seek arrives here as a payload like the rest.
    if (Math.abs(built.getCurrentTime() - seconds) > APART_SECONDS) {
      built.seekTo(seconds, true);
    }
    if (playing) built.playVideo();
    else built.pauseVideo();
  }, [video, playing, muted, seconds]);

  // Everything the player calls, read through a ref. The player outlives every
  // render, so a handler captured when it was built would report the track the
  // widget was on then rather than the one it is on now.
  const latest = useRef({ say, keep, sync });
  useEffect(() => {
    latest.current = { say, keep, sync };
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
          // Off, said outright. Left alone, YouTube turns captions on for
          // anyone whose account asks for them, and a band of subtitles across
          // a music video on the wall is nobody's idea of the board looking
          // right. Asking the player is the only way to say it: YouTube's own
          // caption button is inside an iframe nothing here can reach into.
          cc_load_policy: subtitles.current ? 1 : 0,
          start: Math.floor(from.current),
        },
        events: {
          onReady: () => latest.current.sync(),
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

  // Where it has got to, kept fresh for whoever reports it. A `<video>` says so
  // several times a second on its own; this player has to be asked.
  useEffect(() => {
    const asking = setInterval(() => {
      const built = player.current;
      if (built) latest.current.keep(built.getCurrentTime());
    }, ASK_SECONDS * 1000);
    return () => clearInterval(asking);
  }, []);

  // Two divs on purpose: YouTube replaces the inner one with its iframe, so it
  // has to be a node React is not going to look for again.
  return (
    <div className={className}>
      <div ref={host} className="size-full" />
    </div>
  );
}
