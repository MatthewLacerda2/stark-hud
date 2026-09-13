import { useEffect } from "react";

/**
 * Run something when a key is pressed with the platform's own modifier.
 *
 * Cmd on a Mac, Ctrl everywhere else, which is the only difference anybody
 * expects to matter. Nothing here is on the television — that room has no
 * keyboard — so this is exclusively for somebody at a laptop.
 *
 * Not Cmd+Space, which was the first idea: macOS gives that to Spotlight before
 * a page ever sees it, and a shortcut that works on one machine and silently
 * does nothing on another is worse than a duller one that always works.
 */
export function useHotkey(key: string, run: () => void): void {
  useEffect(() => {
    function pressed(event: KeyboardEvent) {
      if (event.key.toLowerCase() !== key) return;
      if (!event.metaKey && !event.ctrlKey) return;
      // The browser has its own meaning for most of these; taking the key
      // without saying so leaves both things happening at once.
      event.preventDefault();
      run();
    }
    window.addEventListener("keydown", pressed);
    return () => window.removeEventListener("keydown", pressed);
  }, [key, run]);
}
