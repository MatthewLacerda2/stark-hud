import { useSyncExternalStore } from "react";

/**
 * Who is louder while the board is speaking.
 *
 * A spoken line and the music are two different players on the same page: the
 * line is an `Audio` the speech hook makes, the music is the media widget's own
 * element or YouTube's. Nothing connects them, so today a line lands on top of a
 * song and loses — from the sofa you hear that something happened and not what
 * it was, which is worse than the board staying quiet.
 *
 * So the music steps back while the board talks, and this is the whole of the
 * rule both sides agree on. It holds for a run of lines rather than for one:
 * the speech queue plays back to back, and pumping the volume up and down
 * between two sentences is more distracting than either level on its own.
 *
 * Kept outside React deliberately. The speaker and the players sit in different
 * branches with the whole board between them, and threading a prop down through
 * every widget to say "someone is talking" would put this rule in a dozen files
 * that are not about it.
 */

/**
 * How loud the music stays while a line plays.
 *
 * Low enough that a sentence sits clearly on top, high enough that a song is
 * plainly still going — silence would read as the music having stopped, and
 * somebody would go and look for the remote that does not exist.
 */
export const DUCKED = 0.25;

let quiet = false;
const listening = new Set<() => void>();

function announce(next: boolean): void {
  if (quiet === next) return;
  quiet = next;
  for (const tell of listening) tell();
}

/** Step the music back. Said when a run of spoken lines begins. */
export function duck(): void {
  announce(true);
}

/** Put it back. Said when the last line of the run has finished or failed. */
export function unduck(): void {
  announce(false);
}

/** Whether the board is speaking, for whoever is making the other noise. */
export function useDucked(): boolean {
  return useSyncExternalStore(
    (tell) => {
      listening.add(tell);
      return () => listening.delete(tell);
    },
    () => quiet,
    // The board is never speaking before it has been drawn.
    () => false,
  );
}
