import { useEffect } from "react";
import { createRootRoute, Outlet } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

const RELOAD_DELAY_MS = 5000;

/**
 * Nobody is standing at the TV to press reload, so a crash has to heal itself.
 * The message is there for the seconds before the page comes back, and for
 * whoever happens to be looking.
 */
function BoardCrashed() {
  const { t } = useTranslation();
  useEffect(() => {
    const timer = setTimeout(() => location.reload(), RELOAD_DELAY_MS);
    return () => clearTimeout(timer);
  }, []);
  return (
    <main className="flex h-screen w-screen items-center justify-center bg-background">
      <p className="text-h2 text-muted-foreground">{t("board.crashed")}</p>
    </main>
  );
}

/**
 * No chrome: no header, no nav, no padding.
 *
 * The TV is the client and nobody touches it, so every pixel belongs to the
 * board. Anything that needs navigating belongs in a tool, not on this screen.
 */
function RootLayout() {
  return <Outlet />;
}

export const Route = createRootRoute({
  component: RootLayout,
  errorComponent: BoardCrashed,
});
