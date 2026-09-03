import { useEffect, useRef } from "react";
import type { Spoken } from "@/lib/schemas/board";
import { duck, unduck } from "@/lib/ducking";

/**
 * Say out loud what the board has been told to say.
 *
 * The backend runs in a container with no sound card. Sound reaches the
 * television through this page — the browser is the only part of the board
 * wired to a speaker — so the server synthesises a line, serves it by id, and
 * says over the socket that there is something to say. This is the part that
 * makes the noise.
 *
 * Lines are played one at a time, in the order they arrived. Two agents that
 * speak in the same second get two sentences one after the other rather than
 * one noise: overlapping them would make both unintelligible, and there is
 * nobody at the television to ask for a replay.
 *
 * Nothing is drawn, so this is a hook and not a widget. There is no queue on
 * screen and no transport: a line said out loud is gone, the way a line said
 * out loud is.
 *
 * While it is saying anything at all the music steps back, so a line is heard
 * rather than merely noticed. That lasts the whole run rather than one line —
 * see `lib/ducking`.
 */
export function useSpeech(lines: Spoken[]): void {
  /** Lines waiting their turn, oldest first. */
  const waiting = useRef<Spoken[]>([]);
  /** Ids already taken off the board's list, so a re-render never repeats one. */
  const heard = useRef(new Set<string>());
  const speaking = useRef(false);

  useEffect(() => {
    for (const line of lines) {
      if (heard.current.has(line.id)) continue;
      heard.current.add(line.id);
      waiting.current.push(line);
    }

    const next = () => {
      const line = waiting.current.shift();
      if (!line) {
        speaking.current = false;
        unduck();
        return;
      }
      const audio = new Audio(line.url);
      // A line the board has already deleted, or a browser that will not make a
      // sound without a click: either way the queue moves on. One failure must
      // not leave the board mute for the rest of the evening. Both the event
      // and the rejected promise can fire for the same line, so only the first
      // one gets to advance.
      let moved = false;
      const onward = () => {
        if (moved) return;
        moved = true;
        next();
      };
      audio.addEventListener("ended", onward);
      audio.addEventListener("error", onward);
      void audio.play().catch(onward);
    };

    // Nothing to say is not a run: ducking here would step the music back and
    // put it straight back for a board that never opened its mouth.
    if (!speaking.current && waiting.current.length > 0) {
      speaking.current = true;
      duck();
      next();
    }
  }, [lines]);
}
