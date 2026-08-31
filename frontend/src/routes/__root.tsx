import { createRootRoute, Outlet } from "@tanstack/react-router";

/**
 * No chrome: no header, no nav, no padding.
 *
 * The TV is the client and nobody touches it, so every pixel belongs to the
 * board. Anything that needs navigating belongs in a tool, not on this screen.
 */
function RootLayout() {
  return <Outlet />;
}

export const Route = createRootRoute({ component: RootLayout });
