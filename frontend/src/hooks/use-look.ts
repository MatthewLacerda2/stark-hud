import { useMemo, useState } from "react";
import { BLOOM_DIALS, bloomFrom } from "@/lib/bloom";
import { DEPTH_DIALS, depthFrom } from "@/lib/depth";
import {
  dialsOf,
  lookFrom,
  withDial,
  withoutDials,
  type Dial,
} from "@/lib/dials";
import { TAPE_DIALS, tapeFrom } from "@/lib/vhs";

/** Where this browser keeps its look. One key, holding a query string. */
const KEY = "stark-hud:look";

/** Every look the menu turns, in the order it lists them. */
const GROUPS = [TAPE_DIALS, BLOOM_DIALS, DEPTH_DIALS];

const DIALS = dialsOf(GROUPS);

// Storage can be missing or refuse outright — a private window, a browser on a
// television with site data blocked. Neither is a reason for the board not to
// draw, so a failure here is the look this browser never kept.
function kept(): string {
  try {
    return window.localStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

function keep(search: string): void {
  try {
    if (search) window.localStorage.setItem(KEY, search);
    else window.localStorage.removeItem(KEY);
  } catch {
    // Kept for this visit only. The board still shows what was chosen.
  }
}

/**
 * Take dials out of the address once the menu has turned them.
 *
 * The address is laid over what was kept, so a dial left in it would win on
 * the next reload and quietly undo what somebody just chose with the menu.
 */
function forget(dials: Dial[]): void {
  const url = new URL(window.location.href);
  const next = withoutDials(url.search, dials);
  if (next === url.search) return;
  window.history.replaceState(
    window.history.state,
    "",
    `${url.pathname}${next}${url.hash}`,
  );
}

/**
 * The board's look for this browser, and the hand that turns it.
 *
 * Read once when the page opens — what this browser kept, with the address laid
 * over it — and after that changed only by the menu. Each look is parsed from
 * the same query string it always was, and only when that string changes: the
 * lean restarts whenever the depth it is given is a new object, and the page
 * re-renders on every message the socket delivers.
 */
export function useLook() {
  const [search, setSearch] = useState(() =>
    lookFrom(kept(), window.location.search, DIALS),
  );
  const tape = useMemo(() => tapeFrom(search), [search]);
  const bloom = useMemo(() => bloomFrom(search), [search]);
  const depth = useMemo(() => depthFrom(search), [search]);

  function turn(dial: Dial, value: number) {
    const next = withDial(search, dial, value);
    keep(next);
    forget([dial]);
    setSearch(next);
  }

  function reset() {
    keep("");
    forget(DIALS);
    setSearch("");
  }

  return { groups: GROUPS, search, tape, bloom, depth, turn, reset };
}
