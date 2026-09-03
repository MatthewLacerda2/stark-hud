/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [
    tanstackRouter({ target: "react", autoCodeSplitting: true }),
    react(),
    // plugin-react v6 no longer runs Babel itself: the React Compiler is a
    // separate Babel pass. The Rust (`compiler: true`) path is experimental,
    // so we stay on Babel.
    babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
    tsconfigPaths(),
  ],
  // Dev only: the API and the board socket live on the backend port, while
  // Vite serves the app. In production nginx does this instead.
  server: {
    // Exposed on the LAN on purpose: the board is meant to be opened from any
    // device in the house, not just the machine running it. allowedHosts is
    // open for the same reason — the page is reached by IP, by hostname, and
    // by whatever mDNS name a phone resolves.
    host: true,
    allowedHosts: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}", "eslint-rules/**/*.test.ts"],
    // Headroom, not an expectation: nothing here should come close. Several
    // sessions may be running gates on this machine at once, and a test that
    // goes red because the box was busy is a gate that lies. A gate that
    // answers differently twice in a row is not a gate.
    testTimeout: 20_000,
  },
});
