import { useState } from "react";
import { Blend } from "lucide-react";
import { Slider } from "@/components/ui/slider";

/**
 * The per-widget controls that appear while the pointer is on a widget.
 *
 * Marked `no-drag` so the grid ignores pointers here — otherwise reaching for
 * the slider would pick the widget up instead.
 */
export function WidgetControls({
  alpha,
  onPreview,
  onCommit,
}: {
  alpha: number;
  onPreview: (value: number) => void;
  onCommit: (value: number) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="no-drag absolute top-2 right-2 z-10 flex items-center gap-2">
      {open ? (
        <div className="flex w-40 items-center gap-2 rounded-lg bg-popover/90 px-3 py-2 shadow-lg backdrop-blur">
          <Slider
            value={[alpha]}
            min={0}
            max={1}
            step={0.05}
            onValueChange={([value]) => onPreview(value)}
            onValueCommit={([value]) => onCommit(value)}
          />
          <span className="w-8 shrink-0 text-right text-caption text-muted-foreground tabular-nums">
            {Math.round(alpha * 100)}
          </span>
        </div>
      ) : null}
      <button
        type="button"
        aria-label="opacity"
        onClick={() => setOpen((current) => !current)}
        className="rounded-md bg-popover/80 p-1.5 text-muted-foreground shadow-lg backdrop-blur transition-colors hover:text-foreground"
      >
        <Blend className="size-4" />
      </button>
    </div>
  );
}
