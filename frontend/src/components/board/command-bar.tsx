import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useHotkey } from "@/hooks/use-hotkey";
import { ApiError } from "@/lib/api/client";
import { MODELS, runCommand, type CommandModel } from "@/lib/api/command";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

/**
 * A line you type at the board, which the board then does.
 *
 * **This is chrome, and here that is allowed.** Everything else on this board
 * refuses it: a widget is what it shows, and a title bar or a handle is weight
 * that a television across a room cannot use. This appears only when somebody
 * presses a key — and the room the rule is about has no keyboard, so it never
 * appears there at all. It is the same carve-out `CLAUDE.md` makes for hover:
 * chrome is allowed exactly where a person and an input device already are.
 *
 * It closes the moment the sentence is sent. There is nothing to wait around
 * for and nothing to read: the board is the answer, and #80's little panel is
 * already going to spell out beside the new widget what was called to make it.
 * The only thing that keeps this on screen is a failure, because that is the
 * one outcome the board itself cannot show.
 */
export function CommandBar() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [model, setModel] = useState<CommandModel>(MODELS[0].id);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const field = useRef<HTMLInputElement>(null);

  useHotkey(
    "k",
    useCallback(() => setOpen((was) => !was), []),
  );

  // Focus after the bar exists, not while deciding to draw it.
  useEffect(() => {
    if (open) field.current?.focus();
  }, [open]);

  function shut() {
    setOpen(false);
    setPrompt("");
    setFailed(null);
  }

  async function send(event: React.FormEvent) {
    event.preventDefault();
    const said = prompt.trim();
    if (!said || busy) return;
    setBusy(true);
    setFailed(null);
    try {
      await runCommand(said, model);
      shut();
    } catch (error) {
      // The backend answers a refused key, a spent quota or a slow model with
      // one sentence saying what to go and fix. Anything else is the network,
      // and there is nothing useful to add to that.
      setFailed(
        error instanceof ApiError ? error.message : String(error ?? "unknown"),
      );
    } finally {
      setBusy(false);
    }
  }

  if (!open) return null;

  return (
    <div className="absolute inset-x-0 top-[12%] z-50 flex justify-center px-6">
      <form
        onSubmit={send}
        onKeyDown={(event) => event.key === "Escape" && shut()}
        className="flex w-full max-w-[46rem] flex-col gap-2"
      >
        <div className="flex items-center gap-3 rounded-lg border border-border bg-card/85 px-4 py-3 backdrop-blur-sm">
          <Input
            ref={field}
            value={prompt}
            disabled={busy}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder={t("command.placeholder")}
          />
          <Select
            value={model}
            disabled={busy}
            onValueChange={(picked) => setModel(picked as CommandModel)}
          >
            <SelectTrigger aria-label={t("command.model")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MODELS.map((one) => (
                <SelectItem key={one.id} value={one.id}>
                  {one.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Two things the board cannot say for itself: that it is still
            thinking, and that it is not going to happen. */}
        <p
          className={cn(
            "px-1 text-body",
            failed ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {failed
            ? t("command.failed", { reason: failed })
            : busy
              ? t("command.sending")
              : null}
        </p>
      </form>
    </div>
  );
}
