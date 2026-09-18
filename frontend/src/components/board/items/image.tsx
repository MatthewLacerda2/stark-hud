import { useEffect, useRef, useState, type PointerEvent } from "react";
import { useTranslation } from "react-i18next";
import { Maximize } from "lucide-react";
import type { ImagePayload } from "@/lib/schemas/board";
import { Missing } from "@/components/board/items/missing";
import { Button } from "@/components/ui/button";
import { WHOLE, wheelFactor, zoomAt, type View } from "@/lib/zoom";
import { cn } from "@/lib/utils";

/**
 * An image read from a local path. The item id is the handle, not the path.
 *
 * On the board it is the picture and nothing else. With a pointer over it a
 * button appears that fills the screen with it, the way the media widget's
 * does: one browser, one screen, and a real click, because that is the only
 * thing a browser grants fullscreen to. On the television nothing hovers, so
 * the button never appears there.
 *
 * Full screen, the whole picture is fitted rather than cropped, and it can be
 * looked into: the wheel zooms about the pointer, dragging pans, a double
 * click goes back to the whole picture, and Escape leaves — which the browser
 * does for us.
 */
export function Image({ id, payload }: { id: string; payload: ImagePayload }) {
  const { t } = useTranslation();
  const frame = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  const [full, setFull] = useState(false);
  const [view, setView] = useState<View>(WHOLE);
  const held = useRef<{ x: number; y: number } | null>(null);

  // The browser is the one that knows: Escape and its own exit both leave
  // fullscreen without going anywhere near the button.
  useEffect(() => {
    const changed = () => {
      setFull(document.fullscreenElement === frame.current);
      setView(WHOLE);
    };
    document.addEventListener("fullscreenchange", changed);
    return () => document.removeEventListener("fullscreenchange", changed);
  }, []);

  // A native listener rather than `onWheel`: React's is passive, and a wheel
  // that zooms has to stop the page from also scrolling.
  useEffect(() => {
    const element = frame.current;
    if (!element || !full) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const box = element.getBoundingClientRect();
      setView((current) =>
        zoomAt(
          current,
          wheelFactor(event.deltaY),
          event.clientX - box.left,
          event.clientY - box.top,
        ),
      );
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, [full]);

  if (failed) return <Missing path={payload.path} />;

  const grab = (event: PointerEvent<HTMLDivElement>) => {
    if (!full) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    held.current = { x: event.clientX, y: event.clientY };
  };
  const pan = (event: PointerEvent<HTMLDivElement>) => {
    const from = held.current;
    if (!from || view.scale === 1) return;
    held.current = { x: event.clientX, y: event.clientY };
    setView((current) => ({
      ...current,
      x: current.x + event.clientX - from.x,
      y: current.y + event.clientY - from.y,
    }));
  };

  return (
    <div
      ref={frame}
      // Full screen it is the whole page, and a drag in it pans the picture
      // rather than picking the widget up off the board behind it.
      className={cn(
        "group relative size-full overflow-hidden rounded-xl",
        full && "no-drag cursor-grab rounded-none bg-background",
      )}
      onPointerDown={grab}
      onPointerMove={pan}
      onPointerUp={() => (held.current = null)}
      onDoubleClick={() => setView(WHOLE)}
    >
      <img
        src={`/api/v1/media/${id}`}
        alt={payload.alt ?? ""}
        draggable={false}
        onError={() => setFailed(true)}
        className={cn(
          "size-full origin-top-left select-none",
          full ? "object-contain" : "object-cover",
        )}
        style={
          full
            ? {
                transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
              }
            : undefined
        }
      />
      {full ? null : (
        <Button
          variant="ghost"
          size="icon"
          onClick={() =>
            void frame.current?.requestFullscreen().catch(() => {})
          }
          aria-label={t("image.fullscreen")}
          className="no-drag absolute right-3 bottom-3 bg-background/70 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 widget-text"
        >
          <Maximize />
        </Button>
      )}
    </div>
  );
}
