import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Plus } from "lucide-react";
import type { MediaPayload } from "@/lib/schemas/board";
import { createItem } from "@/lib/api/board";
import { ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

/**
 * How big a player a person gets, in grid cells.
 *
 * A cell is square, so this is 16:9 exactly — a film fills it with no bars. At
 * about 60px a cell that is 720x405 on a 1080p monitor: a video somebody means
 * to watch at arm's length, still under a sixth of the board. Not the 10x6 that
 * `add_media` defaults to, which is 5:3 because it has to suit an album as well
 * as a film; a player added by hand starts empty and is nearly always for video.
 */
const SIZE = { w: 12, h: 6.75 };

/** A player with nothing in it, as the server would fill in the defaults. */
const EMPTY: MediaPayload = {
  kind: "media",
  tracks: [],
  index: 0,
  playing: true,
  loop: false,
  muted: false,
  maximised: false,
  captions: false,
  seconds: 0,
  title: null,
};

/**
 * Put an empty player on the board, for whoever is at the pointer to fill.
 *
 * The one widget a person can add by hand, because it is the one widget a
 * person can then fill by hand (`MediaFill`, on the widget's hover). A chart or
 * a panel with no data source behind it is an empty frame, so the rest stay
 * with whoever drives the board.
 *
 * It goes where the board finds room: no position is sent. A full board says
 * no in a sentence saying what is free, and that sentence is shown here rather
 * than swallowed — the board never shrinks or moves anything to make room.
 */
export function AddMedia({ onAdded }: { onAdded: () => void }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<string | null>(null);

  const add = async () => {
    setBusy(true);
    setSaid(null);
    try {
      await createItem({ payload: EMPTY, ...SIZE });
      onAdded();
    } catch (error) {
      setSaid(error instanceof ApiError ? error.message : t("look.lost"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <Button
        variant="ghost"
        size="sm"
        disabled={busy}
        onClick={() => void add()}
        className="self-start"
      >
        <Plus />
        {t("look.addMedia")}
      </Button>
      {said ? (
        <p role="alert" className="text-caption text-destructive">
          {said}
        </p>
      ) : null}
    </div>
  );
}
