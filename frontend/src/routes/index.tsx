import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { boardStatus } from "@/lib/api/board";
import { Background } from "@/components/board/background";
import { BoardGrid } from "@/components/board/board-grid";
import { useBoard } from "@/hooks/use-board";

/**
 * The board. This page is what the TV shows, so it is full-bleed, dark, and has
 * no chrome: nothing here is meant to be clicked.
 */
function BoardPage() {
  const { t } = useTranslation();
  const { items, background, notifications, connected } = useBoard();
  const status = useQuery({
    queryKey: ["board", "status"],
    queryFn: boardStatus,
  });

  const cols = status.data?.cols ?? 12;
  const rows = status.data?.rows ?? 8;

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-background">
      <Background background={background} />

      <div className="relative size-full">
        <BoardGrid
          items={items}
          notifications={notifications}
          cols={cols}
          rows={rows}
        />

        {items.length === 0 && connected ? (
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
