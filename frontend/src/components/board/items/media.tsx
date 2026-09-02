import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Film, Music } from "lucide-react";
import type { MediaPayload, Playback } from "@/lib/schemas/board";
import { reportPlayback } from "@/lib/api/board";
import { YouTubeTrack } from "@/components/board/items/youtube";
import { cn } from "@/lib/utils";

/**
 * Under this, on either axis, the widget stops drawing a player.
 *
 * Four cells is the shorter side of the gauges already on this board, and it is
 * about the point where a title and a position stop being readable from a sofa.
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
 * Nothing here is clickable. Every control is a tool call, because the
 * television has no keyboard and no mouse and a button drawn on this board is a
 * button nobody can press. What arrives is state — which track, playing or not
 * — and this plays what it is told and says what happened.
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
  // What YouTube called the video. Carried with its place in the queue so it
  // cannot be shown against the track after it.
  const [named, setNamed] = useState<{ index: number; title: string } | null>(
    null,
  );

  const say = useCallback(
    (state: Playback["state"], error?: string) => {
      setSaid(state);
      void reportPlayback(id, { state, track: index, error }).catch(() => {});
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

  // An empty queue fires no events, so the one honest thing it can say has to be
  // said outright — otherwise a widget with nothing in it reports nothing at all.
  useEffect(() => {
    if (track) return;
    void reportPlayback(id, { state: "idle" }).catch(() => {});
  }, [track, id]);

  const kept = POSITIONS.get(id);
  const small = cols < PLAYER_CELLS || rows < PLAYER_CELLS;
  const watching = track !== null && track.kind !== "audio" && !small;
  const title = named?.index === index ? named.title : (track?.title ?? null);

  return (
    <div className="relative size-full overflow-hidden rounded-xl widget-surface">
      <video
        ref={element}
        src={
          track && !onYouTube ? `/api/v1/media/${id}/track/${index}` : undefined
        }
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
          startSeconds={kept?.index === index ? kept.seconds : 0}
          say={say}
          keep={(seconds) => POSITIONS.set(id, { index, seconds })}
          name={(found) => setNamed({ index, title: found })}
          className={cn(
            "absolute inset-0",
            // Hidden rather than absent when the widget is too small to watch:
            // making something small is not asking it to go quiet.
            watching ? "size-full" : "size-px opacity-0",
          )}
        />
      ) : null}

      {watching ? null : (
        <div className="absolute inset-0 flex items-center justify-center p-3">
          {track ? (
            <Artwork
              // Keyed on the track so a queue of one album with one missing
              // picture does not lose the picture for every track after it.
              key={index}
              src={
                track.youtube
                  ? `https://i.ytimg.com/vi/${track.youtube}/hqdefault.jpg`
                  : `/api/v1/media/${id}/track/${index}/art`
              }
              video={track.kind !== "audio"}
            />
          ) : (
            <Music className="size-1/2 opacity-40 widget-text" />
          )}
        </div>
      )}

      {small ? null : (
        <div className="absolute inset-x-0 bottom-0 flex flex-col gap-1 bg-background/60 p-4 widget-text">
          {payload.title ? (
            <span className="truncate text-node-sm opacity-70">
              {payload.title}
            </span>
          ) : null}
          <span className="truncate text-node font-semibold">
            {title ?? t("media.emptyQueue")}
          </span>
          <span className="truncate text-node-sm opacity-70">
            {track
              ? t("media.position", {
                  index: index + 1,
                  total: payload.tracks.length,
                })
              : null}
            {said === "playing" ? null : ` · ${t(`media.state.${said}`)}`}
          </span>
        </div>
      )}
    </div>
  );
}
