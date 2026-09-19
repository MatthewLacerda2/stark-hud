import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { boardStatus } from "@/lib/api/board";
import { Background } from "@/components/board/background";
import { BoardGrid } from "@/components/board/board-grid";
import { CommandBar } from "@/components/board/command-bar";
import { VhsFilter } from "@/components/board/vhs-filter";
import { BloomFilter } from "@/components/board/bloom-filter";
import { Stage } from "@/components/board/stage";
import { LookMenu, type MenuAt } from "@/components/board/look-menu";
import { useBoard } from "@/hooks/use-board";
import { useLook } from "@/hooks/use-look";
import { useSpeech } from "@/hooks/use-speech";
import { onBoard } from "@/lib/groups";
import { onPage } from "@/lib/pages";
import { maximisedIn } from "@/lib/maximised";
import { inkVars } from "@/lib/ink";
import { tapeVars } from "@/lib/vhs";
import { cn } from "@/lib/utils";

/**
 * The board. This page is what the TV shows, so it is full-bleed, dark, and has
 * no chrome: nothing here is meant to be clicked. The two exceptions appear only
 * where an input device already is — the command bar on a key, and the look
 * menu on the right mouse button.
 */
function BoardPage() {
  const { t } = useTranslation();
  const {
    items,
    showing,
    background,
    ink,
    notifications,
    wakes,
    reloads,
    origins,
    spoken,
    connected,
  } = useBoard();
  // The board's voice. Nothing is drawn for it: the browser is the only part of
  // this board with a speaker, so saying a line is something the page does
  // rather than something a widget shows.
  useSpeech(spoken);
  // The look — tape, bloom, depth — as this browser keeps it, and the menu that
  // turns it. See `use-look.ts`.
  const look = useLook();
  const [menu, setMenu] = useState<MenuAt | null>(null);
  const closeMenu = useCallback(() => setMenu(null), []);
  const status = useQuery({
    queryKey: ["board", "status"],
    queryFn: boardStatus,
  });

  const cols = status.data?.cols ?? 12;
  const rows = status.data?.rows ?? 8;

  // What is actually on the board: the page that is showing, less whatever is
  // folded away inside a group on it. An open group is a bracket rather than a
  // pane, so it draws nothing either.
  const shown = onBoard(onPage(items, showing));
  // The background is behind everything, so a widget given the whole board hides
  // it completely — and a hidden video is still a video the machine decodes.
  const covered = maximisedIn(shown) !== undefined;

  return (
    <main
      className="relative h-screen w-screen overflow-hidden bg-background"
      style={{ ...tapeVars(look.tape), ...inkVars(ink) }}
      onContextMenu={(event) => {
        // A text field keeps the browser's own menu: that is where paste lives.
        if ((event.target as Element).closest("input, textarea")) return;
        event.preventDefault();
        setMenu({ x: event.clientX, y: event.clientY });
      }}
    >
      <Background background={background} covered={covered} />
      <VhsFilter tape={look.tape} />
      <BloomFilter bloom={look.bloom} />

      {/* The fringe belongs to the content and the rest belongs over it: a
          text-shadow is inherited, so it is set here and every widget inside
          picks it up, while the background video stays outside and unfringed. */}
      <div
        className={cn(
          "relative size-full",
          look.tape.fringe > 0 && "vhs-fringe",
        )}
      >
        <Stage depth={look.depth} still={covered}>
          <BoardGrid
            items={shown}
            everything={items}
            notifications={notifications}
            wakes={wakes}
            reloads={reloads}
            origins={origins}
            tape={look.tape}
            bloom={look.bloom}
            glass={look.depth.glass > 0}
            cols={cols}
            rows={rows}
          />
        </Stage>

        {shown.length === 0 && connected ? (
          <p className="pointer-events-none absolute inset-0 flex items-center justify-center text-h1 text-muted-foreground">
            {t("board.empty")}
          </p>
        ) : null}

        {/* Outside `board-grid.tsx` on purpose: that file is at the top of its
            length budget, and this belongs to the page rather than to the grid
            — it is not a widget and never takes a cell. */}
        <CommandBar />

        {!connected ? (
          <p className="absolute right-4 bottom-3 text-body text-warning">
            {t("board.disconnected")}
          </p>
        ) : null}
      </div>

      {/* Outside the board, so it neither leans with it nor wears the tape. */}
      {menu ? (
        <LookMenu
          at={menu}
          groups={look.groups}
          search={look.search}
          onTurn={look.turn}
          onReset={look.reset}
          onClose={closeMenu}
        />
      ) : null}
    </main>
  );
}

export const Route = createFileRoute("/")({ component: BoardPage });
