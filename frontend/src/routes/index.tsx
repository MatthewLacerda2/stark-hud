import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useCallback } from "react";
import { boardStatus, showPage } from "@/lib/api/board";
import { Background } from "@/components/board/background";
import { BoardGrid } from "@/components/board/board-grid";
import { PageDots } from "@/components/board/page-dots";
import { useBoard } from "@/hooks/use-board";
import { usePageTurn } from "@/hooks/use-page-turn";
import { maximisedIn } from "@/lib/maximised";

/**
 * The board. This page is what the TV shows, so it is full-bleed, dark, and has
 * no chrome: nothing here is meant to be clicked.
 */
function BoardPage() {
  const { t } = useTranslation();
  const { items, background, notifications, page, connected } = useBoard();
  const status = useQuery({
    queryKey: ["board", "status"],
    queryFn: boardStatus,
  });

  const cols = status.data?.cols ?? 12;
  const rows = status.data?.rows ?? 8;

  // Only the pages that have something on them. An extra empty one used to be
  // offered here, the way a phone grows a screen when you drag past the last —
  // but a phone shows you the widget you are dragging, and this board showed a
  // dot that led to an empty grid on a TV nobody can swipe back.
  const pages = items.reduce((most, i) => Math.max(most, i.page), 0) + 1;
  const shown = items.filter((i) => i.page === page);
  // The background is behind everything, so a widget given the whole board hides
  // it completely — and a hidden video is still a video the machine decodes.
  // Asked of the shown page only: a maximised widget on a page nobody is looking
  // at is not drawn, and covers nothing.
  const covered = maximisedIn(shown) !== undefined;

  const go = useCallback((to: number) => {
    // Fire and forget: the socket delivers the new page to every client,
    // including this one, so nothing here has to guess it worked.
    void showPage(Math.max(0, to)).catch(() => {});
  }, []);
  usePageTurn(useCallback((delta: number) => go(page + delta), [go, page]));

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-background">
      <Background background={background} covered={covered} />

      <div className="relative size-full">
        <BoardGrid
          items={shown}
          notifications={notifications}
          cols={cols}
          rows={rows}
        />

        <PageDots page={page} pages={pages} onPick={go} />

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
