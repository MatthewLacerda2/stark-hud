import { useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Plus, Upload } from "lucide-react";
import { handOver, type HandedTrack } from "@/lib/api/board";
import { ApiError } from "@/lib/api/client";
import { uploadTrack } from "@/lib/api/media";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** How far along a hand-over is: a share of a file gone up, or just waiting. */
type Busy = number | "sending" | null;

/**
 * The one way a person with a pointer fills a player without asking a session.
 *
 * A button on hover, and behind it two things: a box to paste a YouTube link
 * into, and a file picker. Either one replaces what the player holds and plays
 * it — somebody pointing at a player and handing it something wants to see
 * *that*, now, not the thing after the rest of the album.
 *
 * It follows the widget's own rule for chrome: it is there on hover, while
 * something inside it has focus, and while a file is going up — and at no other
 * time. A person who has picked a film and taken the pointer away still needs
 * to see that it is going; a person who opened it and wandered off does not
 * need it left on the board. Whatever was typed is kept for the next hover.
 *
 * Nothing here checks a link. The server reads every shape a YouTube link comes
 * in, and when it cannot read one it says why in a sentence, which is shown as
 * it came.
 *
 * Marked `no-drag`, so reaching for it never picks the widget up.
 */
export function MediaFill({ id }: { id: string }) {
  const { t } = useTranslation();
  const picker = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState<Busy>(null);
  const [said, setSaid] = useState<string | null>(null);

  /** Hand the player a track, and put the form away once it has taken it. */
  const hand = async (track: () => Promise<HandedTrack>) => {
    setSaid(null);
    try {
      await handOver(id, await track());
      setOpen(false);
      setLink("");
    } catch (error) {
      // The board's own sentence when it said no; something of ours when the
      // request never got an answer, because a browser's is no use to anyone.
      setSaid(error instanceof ApiError ? error.message : t("media.fill.lost"));
    } finally {
      setBusy(null);
    }
  };

  const paste = (event: FormEvent) => {
    event.preventDefault();
    const text = link.trim();
    if (!text || busy !== null) return;
    setBusy("sending");
    void hand(async () => ({ youtube: text }));
  };

  const pick = (file: File | undefined) => {
    if (!file) return;
    setBusy(0);
    void hand(async () => {
      const got = await uploadTrack(file, setBusy);
      setBusy("sending");
      return { path: got.path };
    });
  };

  return (
    <div
      className={cn(
        "no-drag absolute top-3 right-3 flex flex-col items-end gap-2",
        busy === null &&
          "opacity-0 group-hover:opacity-100 focus-within:opacity-100",
      )}
    >
      <Button
        variant="ghost"
        size="icon"
        aria-label={t("media.fill.open")}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="bg-background/70 widget-text"
      >
        <Plus />
      </Button>
      {open ? (
        <form
          onSubmit={paste}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
          }}
          className="flex w-72 max-w-[calc(100cqw-1.5rem)] flex-col gap-2 rounded-lg bg-popover/90 p-3 text-popover-foreground shadow-lg backdrop-blur"
        >
          <div className="flex items-center gap-2">
            <Input
              autoFocus
              value={link}
              onChange={(event) => setLink(event.target.value)}
              placeholder={t("media.fill.link")}
              aria-label={t("media.fill.link")}
              disabled={busy !== null}
              // Size only. `cn` reads a size token and a colour as the same
              // utility and keeps the last, so the colour comes from the form.
              className="text-body"
            />
            <Button
              type="submit"
              size="sm"
              disabled={busy !== null || !link.trim()}
            >
              {t("media.fill.play")}
            </Button>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={busy !== null}
            onClick={() => picker.current?.click()}
            className="self-start"
          >
            <Upload />
            {t("media.fill.file")}
          </Button>
          <Input
            ref={picker}
            type="file"
            accept="audio/*,video/*"
            aria-label={t("media.fill.file")}
            className="hidden"
            onChange={(event) => {
              pick(event.target.files?.[0]);
              // So picking the same file again after a refusal is a change.
              event.target.value = "";
            }}
          />
          {typeof busy === "number" ? (
            <div
              role="progressbar"
              aria-label={t("media.fill.uploading")}
              aria-valuenow={Math.round(busy * 100)}
              className="flex items-center gap-2"
            >
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary"
                  style={{ width: `${busy * 100}%` }}
                />
              </div>
              <span className="w-9 text-right text-caption text-muted-foreground tabular-nums">
                {Math.round(busy * 100)}%
              </span>
            </div>
          ) : null}
          {said ? (
            <p role="alert" className="text-caption text-destructive">
              {said}
            </p>
          ) : null}
        </form>
      ) : null}
    </div>
  );
}
