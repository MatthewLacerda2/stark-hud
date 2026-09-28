import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { MeshPayload } from "@/lib/schemas/board";
import { ApiError } from "@/lib/api/client";
import { getModel } from "@/lib/api/mesh";
import type { Prepared } from "@/lib/hologram";
import type { Ink, Look, View } from "@/lib/hologram-view";
import { colourUp, formatOf } from "@/lib/mesh";

/**
 * A 3D model, drawn as a hologram — translucent light with glowing edges.
 *
 * The file is fetched once by the widget's id — the path stays on the server —
 * and read in the browser by three.js, which is loaded only when a mesh widget
 * is on the board: it is most of a megabyte, and a board with no models should
 * not pay for it. After that nothing arrives over the wire. The model moves by
 * the browser's own clock, so a turn or an animation goes on through a dropped
 * socket or a restarted backend, the way the countdown goes on counting.
 *
 * Two effects, split by cost. One reads the file and builds the model; it runs
 * when the model changes, which is rarely. The other hands the view a new way
 * of looking at it — camera, colours, explode — and runs whenever the payload
 * does, which for a panel recoloured by load is every few seconds. That split
 * is the whole reason a colour change is cheap.
 */
export function Mesh({
  id,
  payload,
  reload,
}: {
  id: string;
  payload: MeshPayload;
  /**
   * How many times this widget has been told its file was written again.
   *
   * The file is fetched once and the path does not change, so without this a
   * model refined on disk stays the old model on screen — silently, which is
   * the worst of it. Folding the count into the fetch key is the whole of the
   * fix; a different number is a different question.
   */
  reload: number;
}) {
  const { t } = useTranslation();
  const canvas = useRef<HTMLCanvasElement>(null);
  const view = useRef<View | null>(null);
  const [got, setGot] = useState<Fetched | null>(null);

  // Which model this widget is showing, and which telling of it, as one
  // string. The result carries the same string, so what was fetched for a
  // previous model is recognised as stale while it is being rendered rather
  // than cleared by an effect. Note what is NOT in it — the camera, the
  // colours, the size. Those change often, and a drag or a recolour must not
  // drag the file back over the wire with it.
  const asked = `${id}\u0000${payload.path}\u0000${reload}`;
  const found = got?.asked === asked ? got : null;
  const { path } = payload;

  useEffect(() => {
    let live = true;
    load(id, path)
      .then((model) => live && setGot({ asked, model, failed: null }))
      .catch((error: unknown) =>
        live ? setGot({ asked, model: null, failed: reasonOf(error) }) : false,
      );
    return () => {
      live = false;
    };
  }, [id, path, asked]);

  useEffect(() => {
    const element = canvas.current;
    const model = found?.model;
    if (!element || !model) return;
    let made: View | null = null;
    let observer: ResizeObserver | null = null;
    let live = true;
    void import("@/lib/hologram-view").then(({ View: Made }) => {
      if (!live) return;
      made = new Made(element, model);
      view.current = made;
      made.set(lookOf(element, model, payload));
      observer = new ResizeObserver(() =>
        made?.resize(element.clientWidth, element.clientHeight),
      );
      observer.observe(element);
      made.resize(element.clientWidth, element.clientHeight);
    });
    return () => {
      live = false;
      observer?.disconnect();
      made?.dispose();
      view.current = null;
    };
    // The payload is read once here for the first frame; after that the effect
    // below carries it, so a recolour does not rebuild the view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [found]);

  useEffect(() => {
    const element = canvas.current;
    const model = found?.model;
    if (element && model) view.current?.set(lookOf(element, model, payload));
  }, [found, payload]);

  if (found?.failed)
    return (
      <div className="flex size-full flex-col items-center justify-center gap-2 rounded-xl bg-background p-[3.5cqmin]">
        <span className="text-node text-foreground">{t("mesh.wontDraw")}</span>
        <span className="max-w-full truncate text-node-sm text-muted-foreground">
          {found.failed}
        </span>
      </div>
    );

  return (
    <canvas
      // One canvas per telling of the model. A view lets go of the GPU by
      // losing its context on purpose, and a canvas hands that same lost
      // context to whatever asks it next — so a view built on the old element
      // after a reload drew nothing at all. A new key is a new element.
      key={asked}
      ref={canvas}
      // `widget-text` is not decoration here: it is how the canvas is told what
      // colour to draw in. The colour is read back off this element's computed
      // style, so the board's ink and a colour set on this one widget both
      // reach the model without either being restated in JavaScript.
      className="size-full rounded-xl widget-text"
    />
  );
}

/** Fetch a model's file and make it into light, loading three.js to do it. */
async function load(id: string, path: string): Promise<Prepared> {
  const format = formatOf(path);
  if (format === null) throw new Error(`Not a model file: ${path}`);
  const [bytes, { prepare }] = await Promise.all([
    getModel(id),
    import("@/lib/hologram"),
  ]);
  return prepare(bytes, format);
}

/**
 * The payload, as the view wants it: numbers, and every colour already mixed.
 *
 * Colours are resolved here and not per frame: resolving a token is a
 * getComputedStyle, which is a layout read no frame should be doing, and the
 * answer cannot change until the payload does.
 */
function lookOf(
  element: HTMLElement,
  model: Prepared,
  payload: MeshPayload,
): Look {
  const read = inkReader();
  const ink = inkOf(element, read, "", [255, 255, 255]);
  const pinned = model.drawables.map((drawable) => {
    const rule = colourUp(drawable.names, payload.colors);
    return rule === null ? null : inkOf(element, read, rule, ink);
  });
  const { wave } = payload;
  return {
    spin: payload.spin,
    sweep: payload.sweep,
    heading: payload.heading,
    tilt: payload.tilt,
    fov: payload.fov,
    zoom: payload.zoom,
    panX: payload.pan_x,
    panY: payload.pan_y,
    explode: payload.explode,
    ink,
    pinned,
    wave: wave
      ? {
          mode: wave.mode,
          seconds: wave.seconds,
          spread: wave.spread,
          ramp: wave.colors.map((c) => inkOf(element, read, c, ink)),
        }
      : null,
  };
}

/** What one widget's fetch came back with, and which model it was for. */
type Fetched = {
  asked: string;
  model: Prepared | null;
  /**
   * The sentence to draw instead of the model, or null when there is nothing to
   * draw and nothing to say.
   *
   * A 404 leaves this null on purpose. It means the file is gone, the backend
   * has already taken this widget off the board, and the socket is about to say
   * so — putting "file not found" on screen for that moment would be a card
   * that flashes up and vanishes, which reads as a fault rather than as the
   * removal it is. What is worth drawing is the other answer: a file that is
   * there and cannot be drawn, which nothing else will ever mention.
   */
  failed: string | null;
};

/** The sentence the backend sent, for the failures worth showing. */
function reasonOf(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.status === 404) return null;
  return error.message;
}

/**
 * Turn anything the board calls a colour into numbers, by asking the browser.
 *
 * Two questions, and each goes to the thing that can actually answer it.
 *
 * The board's palette arrives as `var(--color-info)`, which is not a colour
 * until something resolves it against the stylesheet — and what it resolves to
 * follows the theme, which is the whole point of a token over a hex. Only the
 * document knows that, so the value is set on a real element inside the widget
 * and read back.
 *
 * What comes back is then whatever CSS colour syntax the palette was written
 * in, and this board's is written in `oklch()`. Reading that with a regex for
 * `rgb()` is what broke the first version of this: every colour missed, every
 * part fell through to the fallback, and the model drew a uniform white while
 * the wave ran underneath it doing nothing anybody could see. So the parsing
 * goes to the thing that can parse any of it — paint one pixel and look at the
 * pixel. A canvas has to understand every colour CSS has, and unlike a regex it
 * cannot be behind by one colour space.
 */
function inkReader(): (value: string) => Ink | null {
  const scratch = document.createElement("canvas");
  scratch.width = 1;
  scratch.height = 1;
  const ctx = scratch.getContext("2d", { willReadFrequently: true });
  return (value: string) => {
    if (!ctx || !value) return null;
    // Cleared first, so a value the canvas cannot parse leaves the previous
    // colour behind rather than the one before it — a silent wrong colour is
    // the failure this whole function exists to stop.
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = "#000";
    ctx.fillStyle = value;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
    return [r, g, b];
  };
}

/** One colour the board named, as numbers, or the widget's own ink instead. */
function inkOf(
  probe: HTMLElement,
  read: (value: string) => Ink | null,
  value: string,
  fallback: Ink,
): Ink {
  const had = probe.style.color;
  probe.style.color = "";
  probe.style.color = value;
  const computed = getComputedStyle(probe).color;
  // Put the element back as it was found. Leaving an inline colour on the
  // canvas would override the `widget-text` class it takes its default from,
  // so the next read would return this colour rather than the board's ink.
  probe.style.color = had;
  return read(computed) ?? fallback;
}
