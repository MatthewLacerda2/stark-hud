/**
 * Typing at the board.
 *
 * Everything on this board is put there by a Claude session, and that stays
 * true. This is a second, much faster way in for small imperative changes —
 * *move the clock to the left* — which should not have to cost a large model's
 * whole turn. The backend sends the sentence to one of Google's Flash models
 * with the board's own tools attached and runs whatever it calls.
 *
 * Nothing is rendered from what comes back. The board is the answer: if a
 * widget moved, you saw it move. What is here is for the bar to know the work
 * happened, and for one sentence when it did not.
 */
import { request } from "@/lib/api/client";

/**
 * The models a prompt may go to. Mirrored by hand from
 * `backend/schemas/command.py`, like everything else in `lib/schemas` — nothing
 * checks that the two agree.
 *
 * Both are Flash, because the entire reason this exists beside Claude is
 * speed. The Live API is deliberately absent: it is a stateful WebSocket built
 * for real-time audio, and none of that buys anything for a typed one-shot.
 */
export type CommandModel = "gemini-3.5-flash-lite" | "gemini-3.8-flash";

/**
 * What the dropdown offers, in the order it offers it.
 *
 * The label is what it costs and how clever it is, in as few words as fit on a
 * line — nobody picking one of these wants a model name, they want to know
 * whether this sentence needs the expensive one.
 */
export const MODELS: { id: CommandModel; label: string }[] = [
  { id: "gemini-3.5-flash-lite", label: "Flash Lite 3.5" },
  { id: "gemini-3.8-flash", label: "Flash 3.8" },
];

/** One tool the model called, and the line that tool answered with. */
export interface CommandCall {
  tool: string;
  said: string;
}

/** What running one instruction did. */
export interface CommandRead {
  model: string;
  calls: CommandCall[];
  /** Wall clock for the whole thing. The number this feature is judged by. */
  took_ms: number;
}

/** Send one instruction to the board and wait for it to have been carried out. */
export function runCommand(
  prompt: string,
  model: CommandModel,
): Promise<CommandRead> {
  return request<CommandRead>("/command", {
    method: "POST",
    body: { prompt, model },
  });
}
