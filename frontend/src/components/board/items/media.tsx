import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import { useTranslation } from "react-i18next";
import { Film, Maximize, Minimize, Music } from "lucide-react";
import type { MediaPayload, Playback } from "@/lib/schemas/board";
import { reportPlayback } from "@/lib/api/board";
import { YouTubeTrack } from "@/components/board/items/youtube";
import { APART_SECONDS, TICK_SECONDS } from "@/lib/playback";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Under this, on either axis, the widget stops drawing a player.
 *
 * Four cells is the shorter side of the gauges already on this board, and it is
 * about the point where a line of text stops being readable from a sofa.
 * Smaller than that the widget is a thumbnail — and it keeps playing, because
 * making something small is not asking it to go quiet.
 */
const PLAYER_CELLS = 4;

/**
 * Where each widget had got to, kept outside React.
 *
 * Maximising moves the player out of its grid cell and into a layer over the
 * whole board, which is a different parent and therefore a new element. Without
 * this, asking for a bigger picture would restart the track.
 */
const POSITIONS = new Map<string, { index: number; seconds: number }>();

/**
 * Where the browser fetches a track's bytes, or the picture beside it.
 *
 * The stamp on the end is the whole reason this is a function. A track is
 * addressed by the widget's id and its place in the queue, so replacing a queue
 * leaves index 0 sitting behind the identical URL over entirely different bytes
 * — and the browser, quite correctly, goes on playing the file it already has,
 * right down to reporting the old one's duration. A URL that changes when the
 * file changes is the one thing a cache cannot argue with.
 */
function trackUrl(
  id: string,
  index: number,
  stamp: string | null,
  part: "" | "/art" = "",
): string {
  const url = `/api/v1/media/${id}/track/${index}${part}`;
  return stamp ? `${url}?v=${stamp}` : url;
}

/**
 * Why a media element gave up, in the browser's own vocabulary.
 *
 * Sent as-is rather than translated: this goes to whoever is driving the board,
 * not to the room, and "decode" is the word that tells them the file is fine and
 * the codec is not.
 */
function whyItFailed(media: HTMLVideoElement): string {
  const reasons = ["aborted", "network", "decode", "unsupported source"];
  return reasons[(media.error?.code ?? 0) - 1] ?? "unknown";
}

/**
 * The picture beside a track, falling back to a symbol for what it is.
 *
 * For a file that is whatever the ripper left in the folder; for a YouTube video
 * it is YouTube's own thumbnail, which is the one picture a video id always has.
 */
function Artwork({ src, video }: { src: string; video: boolean }) {
  const [failed, setFailed] = useState(false);
  // Named anything but `Symbol`: shadowing the global one breaks React itself.
  const Glyph = video ? Film : Music;
  if (failed) {
    return <Glyph className="size-1/2 opacity-40 widget-text" />;
  }
  return (
    <img
      src={src}
      alt=""
      onError={() => setFailed(true)}
      className="size-full rounded-xl object-contain"
    />
  );
}

/**
 * Fill the screen with this widget, and give the screen back.
 *
 * This is not `maximised`. That flag is board state: every viewer shares it, it
 * grows the widget inside the grid, and a session sets it with a call. This is
 * one browser filling one screen, and it is deliberately not reachable from a
 * call at all — browsers grant fullscreen only from a real user gesture, so the
 * only shape it can take is a button somebody presses. Escape leaves it, which
 * the browser does for us.
 *
 * It appears on hover, and on the television it therefore never appears: there
 * is no keyboard, no mouse and no pointer there, so nothing ever hovers. That is
 * the whole of the handling this needs — do not "fix" it with a size check or a
 * media query, and do not draw it always to make it easier to find.
 */
function FullScreen({ frame }: { frame: RefObject<HTMLDivElement | null> }) {
  const { t } = useTranslation();
  const [full, setFull] = useState(false);

  // The browser is the one that knows: Escape and the browser's own exit both
  // leave fullscreen without going anywhere near this button.
  useEffect(() => {
    const changed = () => setFull(document.fullscreenElement === frame.current);
    document.addEventListener("fullscreenchange", changed);
    return () => document.removeEventListener("fullscreenchange", changed);
  }, [frame]);

  const toggle = () => {
    if (document.fullscreenElement) {
      void document.exitFullscreen().catch(() => {});
      return;
    }
    void frame.current?.requestFullscreen().catch(() => {});
  };

  const Glyph = full ? Minimize : Maximize;
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      aria-label={t(full ? "media.leaveFullscreen" : "media.fullscreen")}
      className="absolute right-3 bottom-3 bg-background/70 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 widget-text"
    >
      <Glyph />
    </Button>
  );
}

/**
 * A queue of audio, video and YouTube that plays itself through.
 *
 * One widget for all of them because everything a queue needs — an order, a
 * place in it, a transport, a loop — is the same whatever a track turns out to
 * be; the only differences are whether there is anything to look at while it
 * plays and who does the playing. So there is one media element, a `<video>`,
 * for every local track whichever kind it is: it never changes type, so a queue
 * can hold both and moving between them does not tear the player down. An audio
 * track simply gives it nothing to show, and the art takes the space.
 *
 * A YouTube video cannot go in that element — there is no URL for it, and no
 * API key here to ask for one — so it is played beside it by YouTube's own
 * player, which is mounted only while the widget is on such a track. That is the
 * whole of the difference: the transport, the report and the queue are shared,
 * and a queue may mix the two freely.
 *
 * What it draws is decided by what is playing. A video is video and nothing
 * else: no title over it, no queue position under it, nothing but the picture.
 * Audio has a picture to sit still on, so it gets the album art with the track's
 * title above and the artist and album below, all of it read off the file's own
 * tags on the server. Neither of them narrates the transport at anybody: a
 * player that says "playing" while it is plainly playing is debug text on a
 * television.
 *
 * Nothing here is a control, with one exception, and the exception proves the
 * rule: every transport verb is a tool call, because the television has no
 * keyboard and no mouse and a button drawn on this board is a button nobody can
 * press. Fullscreen is the one thing a call cannot do — a browser grants it only
 * to a gesture — so it is a button, and it is only ever visible to a pointer.
 *
 * Saying what happened is the only thing on this board that runs back to the
 * server. A file may be gone or in a codec this browser will not decode, and
 * only the page can find that out; without sending it, the failure would be
 * visible from the sofa and nowhere else. A finished track goes back the same
 * way, and the server decides what follows it.
 */
export function Media({
  id,
  payload,
  cols,
  rows,
}: {
  id: string;
  payload: MediaPayload;
  cols: number;
  rows: number;
}) {
  const { t } = useTranslation();
  const frame = useRef<HTMLDivElement>(null);
  const element = useRef<HTMLVideoElement>(null);
  // What this widget last saw itself do. Seeded from what it was told to do, so
  // a page that has just loaded reads correctly before the first event fires.
  const [said, setSaid] = useState<Playback["state"]>(() => {
    if (payload.tracks.length === 0) return "idle";
    return payload.playing ? "playing" : "paused";
  });

  const track = payload.tracks[payload.index] ?? null;
  const index = payload.index;
  // The video id when the widget is on a YouTube track, and nothing when it is
  // not — which is also how the rest of this file asks which kind it is on.
  const video = track?.kind === "youtube" ? track.youtube : null;
  const onYouTube = video !== null;

  const say = useCallback(
    (state: Playback["state"], error?: string) => {
      setSaid(state);
      // Where it stopped travels with what it did, so a pause is remembered to
      // the second rather than to the last tick. Nothing is said about zero: it
      // is what the board already holds, and a track that has not started yet
      // must not overwrite a place somebody has just asked for.
      const here = POSITIONS.get(id);
      const seconds =
        here?.index === index && here.seconds > 0 ? here.seconds : undefined;
      void reportPlayback(id, { state, track: index, error, seconds }).catch(
        () => {},
      );
    },
    [id, index],
  );

  // What this element says only speaks for the widget while the widget is on a
  // local track. On a YouTube one it is being emptied and stopped, and the
  // events that come out of that are about the file it has just left.
  const fromFile = (state: Playback["state"], error?: string) => {
    if (!onYouTube) say(state, error);
  };

  // Play or pause to match what the board says. The track's path is a dependency
  // as well as the flag: a new source arrives paused and has to be started.
  useEffect(() => {
    const media = element.current;
    if (!media) return;
    // A YouTube track leaves this element with no source — and stopped, because
    // taking the source away does not stop what is already decoding, and an
    // album playing on underneath a video is the worst of both.
    if (!track || onYouTube) {
      if (!media.paused) media.pause();
      return;
    }
    // Asked each time the board changes, so both sides check first: calling play
    // on something already playing is noise, and pause on something paused is a
    // spurious event travelling back to the server.
    if (payload.playing && media.paused) void media.play().catch(() => {});
    if (!payload.playing && !media.paused) media.pause();
  }, [payload.playing, index, track, onYouTube]);

  // Pick up where this widget was before it was moved between layers.
  useEffect(() => {
    const media = element.current;
    const kept = POSITIONS.get(id);
    if (media && kept && kept.index === index) media.currentTime = kept.seconds;
    // Mount only: at any other time this would fight the person listening.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Go where the board says, when the board says somewhere this element is not.
  // Somebody asking for the third hour of a film has no other way in — the
  // television has nothing to drag — and a page that has just loaded is at zero
  // while the board still knows where the film was.
  useEffect(() => {
    const media = element.current;
    if (!media || !track || onYouTube) return;
    if (Math.abs(media.currentTime - payload.seconds) > APART_SECONDS) {
      media.currentTime = payload.seconds;
    }
  }, [payload.seconds, index, track, onYouTube]);

  // Say where it has got to, every so often, so a reload and a restart both come
  // back here rather than to the beginning. Only while it is playing: a paused
  // widget is not moving, and the last tick already said where it stopped.
  useEffect(() => {
    if (!track || !payload.playing) return;
    const tick = setInterval(() => {
      const here = POSITIONS.get(id);
      if (here?.index !== index || here.seconds <= 0) return;
      void reportPlayback(id, {
        state: "playing",
        track: index,
        seconds: here.seconds,
      }).catch(() => {});
    }, TICK_SECONDS * 1000);
    return () => clearInterval(tick);
  }, [id, index, track, payload.playing]);

  // An empty queue fires no events, so the one honest thing it can say has to be
  // said outright — otherwise a widget with nothing in it reports nothing at all.
  useEffect(() => {
    if (track) return;
    void reportPlayback(id, { state: "idle" }).catch(() => {});
  }, [track, id]);

  const kept = POSITIONS.get(id);
  const small = cols < PLAYER_CELLS || rows < PLAYER_CELLS;
  const watching = track !== null && track.kind !== "audio" && !small;
  // Who is playing and what record this is, in the one line under the art. The
  // album falls back to the name the queue was given, so a folder of untagged
  // files still says what it is; a track that knows neither draws no line at
  // all, rather than a row of labels with nothing beside them.
  const credit = [track?.artist, track?.album ?? payload.title]
    .filter((part): part is string => Boolean(part))
    .join(" · ");
  // A failure takes that line instead. It is the only thing the widget ever says
  // about itself, and only where there is room for it to be read — over a video
  // it says nothing, because a video is video, and the report has already gone
  // to whoever can do something about it.
  const under = track
    ? said === "failed"
      ? t("media.wontPlay")
      : credit
    : t("media.emptyQueue");

  return (
    <div
      ref={frame}
      className="group relative size-full overflow-hidden rounded-xl widget-surface"
    >
      <video
        ref={element}
        src={track && !onYouTube ? trackUrl(id, index, track.stamp) : undefined}
        muted={payload.muted}
        playsInline
        onPlay={() => fromFile("playing")}
        onPause={() => fromFile("paused")}
        onEnded={() => fromFile("ended")}
        onError={(event) =>
          fromFile("failed", whyItFailed(event.currentTarget))
        }
        onTimeUpdate={(event) =>
          POSITIONS.set(id, {
            index,
            seconds: event.currentTarget.currentTime,
          })
        }
        className={cn(
          "absolute inset-0",
          // Hidden rather than absent when there is nothing to watch: this is
          // the thing that is playing, and taking it out would stop the music.
          watching && !onYouTube
            ? "size-full object-contain"
            : "size-px opacity-0",
        )}
      />

      {video ? (
        <YouTubeTrack
          video={video}
          playing={payload.playing}
          muted={payload.muted}
          captions={payload.captions}
          seconds={payload.seconds}
          startSeconds={kept?.index === index ? kept.seconds : payload.seconds}
          say={say}
          keep={(seconds) => POSITIONS.set(id, { index, seconds })}
          className={cn(
            "absolute inset-0",
            // Hidden rather than absent when the widget is too small to watch:
            // making something small is not asking it to go quiet.
            watching ? "size-full" : "size-px opacity-0",
          )}
        />
      ) : null}

      {watching ? null : (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-3 widget-text">
          {small || !track ? null : (
            <span className="w-full truncate text-center text-node font-semibold">
              {track.title}
            </span>
          )}
          <div className="flex min-h-0 w-full flex-1 items-center justify-center">
            {track ? (
              <Artwork
                // Keyed on the track so a queue of one album with one missing
                // picture does not lose the picture for every track after it.
                key={index}
                src={
                  track.youtube
                    ? `https://i.ytimg.com/vi/${track.youtube}/hqdefault.jpg`
                    : trackUrl(id, index, track.stamp, "/art")
                }
                video={track.kind !== "audio"}
              />
            ) : (
              <Music className="size-1/2 opacity-40 widget-text" />
            )}
          </div>
          {small || !under ? null : (
            <span className="w-full truncate text-center text-node-sm opacity-70">
              {under}
            </span>
          )}
        </div>
      )}

      {track ? <FullScreen frame={frame} /> : null}
    </div>
  );
}
