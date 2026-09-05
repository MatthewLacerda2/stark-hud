import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { boardStatus } from "@/lib/api/board";
import { Background } from "@/components/board/background";
import { BoardGrid } from "@/components/board/board-grid";
import { VhsFilter } from "@/components/board/vhs-filter";
import { BloomFilter } from "@/components/board/bloom-filter";
import { useBoard } from "@/hooks/use-board";
import { useSpeech } from "@/hooks/use-speech";
import { onBoard } from "@/lib/groups";
import { maximisedIn } from "@/lib/maximised";
import { inkVars } from "@/lib/ink";
import { tapeFrom, tapeVars } from "@/lib/vhs";
import { bloomFrom } from "@/lib/bloom";
import { cn } from "@/lib/utils";

// Read once, when the module loads. The board has exactly one route and no way
// to navigate within it, so the only thing that can change the look is a
// reload — which is also how someone judging it from a phone will change it.
const TAPE = tapeFrom(window.location.search);
// Read the same way and for the same reason: a television across the room, and a
// number somebody can type instead of a rebuild for every guess.
const BLOOM = bloomFrom(window.location.search);

/**
 * The board. This page is what the TV shows, so it is full-bleed, dark, and has
 * no chrome: nothing here is meant to be clicked.
 */
function BoardPage() {
  const { t } = useTranslation();
  const { items, background, ink, notifications, wakes, spoken, connected } =
    useBoard();
  // The board's voice. Nothing is drawn for it: the browser is the only part of
  // this board with a speaker, so saying a line is something the page does
  // rather than something a widget shows.
  useSpeech(spoken);
  const status = useQuery({
    queryKey: ["board", "status"],
    queryFn: boardStatus,
  });

  const cols = status.data?.cols ?? 12;
  const rows = status.data?.rows ?? 8;

  // What is actually on the board. A widget inside a folded group is not, and
  // neither is an open group, which is a bracket rather than a pane.
  const shown = onBoard(items);
  // The background is behind everything, so a widget given the whole board hides
  // it completely — and a hidden video is still a video the machine decodes.
  const covered = maximisedIn(shown) !== undefined;

  return (
    <main
      className="relative h-screen w-screen overflow-hidden bg-background"
      style={{ ...tapeVars(TAPE), ...inkVars(ink) }}
    >
      <Background background={background} covered={covered} />
      <VhsFilter tape={TAPE} />
      <BloomFilter bloom={BLOOM} />

      {/* The fringe belongs to the content and the rest belongs over it: a
          text-shadow is inherited, so it is set here and every widget inside
          picks it up, while the background video stays outside and unfringed. */}
      <div
        className={cn("relative size-full", TAPE.fringe > 0 && "vhs-fringe")}
      >
        <BoardGrid
          items={shown}
          everything={items}
          notifications={notifications}
          wakes={wakes}
          tape={TAPE}
          bloom={BLOOM}
          cols={cols}
          rows={rows}
        />

        {shown.length === 0 && connected ? (
          <p className="pointer-events-none absolute inset-0 flex items-center justify-center text-h1 text-muted-foreground">
            {t("board.empty")}
          </p>
        ) : null}

        {!connected ? (
          <p className="absolute right-4 bottom-3 text-body text-warning">
            {t("board.disconnected")}
          </p>
        ) : null}
      </div>
    </main>
  );
}

export const Route = createFileRoute("/")({ component: BoardPage });
