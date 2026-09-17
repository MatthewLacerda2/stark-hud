import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Slider } from "@/components/ui/slider";
import { dialValue, type Dial, type DialGroup } from "@/lib/dials";
import { cn } from "@/lib/utils";

/** How finely a dial turns. A hundredth is finer than anybody can see. */
const STEP = 0.05;

/** Where the pointer was when the menu was asked for, in viewport pixels. */
export type MenuAt = { x: number; y: number };

/**
 * The board's look, turned by hand: tape, bloom and depth.
 *
 * Opened with the right mouse button anywhere on the board, which is chrome in
 * exactly the place `CLAUDE.md` allows it — where a pointer exists, and so never
 * on the television. Everything here is board-wide. There is nothing per widget
 * in it, because nothing about a widget is a look somebody sets from a menu.
 *
 * It opens towards the middle of the screen from wherever the pointer was, so a
 * click near an edge never puts half of it off the screen, and it shuts on
 * Escape or on a press anywhere else.
 */
export function LookMenu({
  at,
  groups,
  search,
  onTurn,
  onReset,
  onClose,
}: {
  at: MenuAt;
  groups: DialGroup[];
  /** The look as it stands, as a query string. */
  search: string;
  onTurn: (dial: Dial, value: number) => void;
  onReset: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const press = (event: PointerEvent) => {
      if (!panel.current?.contains(event.target as Node)) onClose();
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("pointerdown", press);
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("pointerdown", press);
      window.removeEventListener("keydown", key);
    };
  }, [onClose]);

  const right = at.x > window.innerWidth / 2;
  const below = at.y > window.innerHeight / 2;
  const place: React.CSSProperties = {
    ...(right ? { right: window.innerWidth - at.x } : { left: at.x }),
    ...(below ? { bottom: window.innerHeight - at.y } : { top: at.y }),
  };

  const row = (dial: Dial, master: boolean) => {
    const value = dialValue(search, dial);
    return (
      <label key={dial.param} className="flex items-center gap-3">
        <span
          className={cn(
            "w-24 shrink-0",
            master
              ? "text-body text-foreground"
              : "pl-3 text-caption text-muted-foreground",
          )}
        >
          {t(`look.${dial.param}`)}
        </span>
        <Slider
          value={[value]}
          min={0}
          max={dial.ceiling}
          step={STEP}
          onValueChange={([turned]) =>
            onTurn(dial, Math.round(turned * 100) / 100)
          }
        />
        <span className="w-9 shrink-0 text-right text-caption text-muted-foreground tabular-nums">
          {value.toFixed(2)}
        </span>
      </label>
    );
  };

  return (
    <div
      ref={panel}
      role="dialog"
      aria-label={t("look.title")}
      className="no-drag fixed z-50 flex max-h-[calc(100vh-1rem)] w-80 flex-col gap-4 overflow-y-auto rounded-lg bg-popover/90 p-4 shadow-lg backdrop-blur"
      style={place}
      onContextMenu={(event) => {
        // A right click inside the menu is somebody using the menu.
        event.preventDefault();
        event.stopPropagation();
      }}
    >
      {groups.map((group) => (
        <div key={group.name} className="flex flex-col gap-2">
          {row(group.master, true)}
          {group.parts.map((part) => row(part, false))}
        </div>
      ))}
      <button
        type="button"
        onClick={onReset}
        className="self-end text-caption text-muted-foreground transition-colors hover:text-foreground"
      >
        {t("look.reset")}
      </button>
    </div>
  );
}
