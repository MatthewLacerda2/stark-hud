import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { MeshPayload, Wireframe } from "@/lib/schemas/board";
import { ApiError } from "@/lib/api/client";
import { getWireframe } from "@/lib/api/mesh";
import {
  BANDS,
  bandAt,
  bandFade,
  camera,
  colourFor,
  layout,
  phases,
  project,
  rampAt,
} from "@/lib/mesh";

/** How wide the halo pass is drawn, against the bright pass over it. */
const HALO_WIDTH = 3.5;

/** How much of the halo is actually laid down. */
const HALO_ALPHA = 0.22;

/**
 * A 3D model, drawn as a turning wireframe.
 *
 * The geometry is fetched once by the widget's id — the path stays on the
 * server — and after that nothing arrives over the wire. The model turns from
 * the browser's own clock, so it goes on turning through a dropped socket, a
 * reload, or a backend that has been restarted underneath it, the way the
 * countdown goes on counting.
 *
 * The glow is drawn here rather than borrowed from the board's bloom filter,
 * for two reasons and both of them decide it. The board's bloom is off unless
 * somebody asks for it with `?bloom=`, and a hologram with no light is a
 * drawing of a hologram. And the filter is an SVG one over the widget's whole
 * region, which re-runs every time the widget repaints — sixty times a second
 * here, which is precisely the cost the tape was rewritten to stop paying. Two
 * passes of the same lines, one wide and faint and one tight and bright, is the
 * same effect for the price of one extra stroke per depth band.
 */
export function Mesh({ id, payload }: { id: string; payload: MeshPayload }) {
  const { t } = useTranslation();
  const canvas = useRef<HTMLCanvasElement>(null);
  const [got, setGot] = useState<Fetched | null>(null);

  // Which model this widget is showing, as one string. The result carries the
  // same string, so what was fetched for a previous model is recognised as
  // stale while it is being rendered rather than cleared by an effect — the
  // answer the countdown gives to state that has to follow what was just
  // worked out. The path is in the key because a widget that ever learns to
  // change it should refetch rather than go on drawing the model it had.
  const asked = `${id}\u0000${payload.path}`;
  const found = got?.asked === asked ? got : null;

  useEffect(() => {
    let live = true;
    getWireframe(id)
      .then((wire) => live && setGot({ asked, wire, failed: null }))
      .catch((error: unknown) =>
        live ? setGot({ asked, wire: null, failed: reasonOf(error) }) : false,
      );
    return () => {
      live = false;
    };
  }, [id, asked]);

  useEffect(() => {
    const element = canvas.current;
    if (!element || !found?.wire) return;
    return spin(element, found.wire, payload);
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
      ref={canvas}
      // `widget-text` is not decoration here: it is how the canvas is told what
      // colour to draw in. The stroke colour is read back off this element's
      // computed style, so the board's ink and a colour set on this one widget
      // both reach the lines without either being restated in JavaScript.
      className="size-full rounded-xl widget-text"
    />
  );
}

/** What one widget's fetch came back with, and which model it was for. */
type Fetched = {
  asked: string;
  wire: Wireframe | null;
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

/** A colour as the numbers needed to mix it: red, green, blue, 0-255. */
type Ink = [number, number, number];

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

/** Two inks blended, as something canvas will take as a stroke. */
function mixed(from: Ink, to: Ink, mix: number): string {
  const at = (i: number) => Math.round(from[i] + (to[i] - from[i]) * mix);
  return `rgb(${at(0)} ${at(1)} ${at(2)})`;
}

/**
 * Draw the model, and keep drawing it. Returns the teardown.
 *
 * Split out of the component because it is a loop over typed arrays and a
 * canvas, and reading it next to JSX helps nobody. Everything it needs that
 * does not change per frame — the parts, where they have moved to, how far the
 * model reaches, how big a pixel is — is worked out once, up here.
 */
function spin(
  element: HTMLCanvasElement,
  wire: Wireframe,
  payload: MeshPayload,
): () => void {
  const context = element.getContext("2d");
  if (!context) return () => {};

  const { moved, bounds } = layout(wire.parts, payload.explode, payload.tilt);
  const read = inkReader();
  const base = inkOf(element, read, "", [255, 255, 255]);
  const ink = `rgb(${base[0]} ${base[1]} ${base[2]})`;

  // What colour each part is pinned to, worked out once. A part named in
  // `colors` keeps that colour and sits out the wave; everything else takes the
  // wave, and anything the wave skips falls back to the widget's own ink.
  // Resolved here and not per frame: the answer cannot change until the payload
  // does, and resolving a token means a getComputedStyle, which is a layout
  // read no frame should be doing.
  const pinned = wire.parts.map((part) => {
    const rule = colourFor(part.name, payload.colors);
    if (rule === null) return null;
    const [r, g, b] = inkOf(element, read, rule, base);
    return `rgb(${r} ${g} ${b})`;
  });
  const wave = payload.wave;
  const ramp = wave
    ? wave.colors.map((c) => inkOf(element, read, c, base))
    : [];
  const phase = wave ? phases(wire.parts, wave.mode) : [];
  // One scratch array per part, reused every frame. The alternative is
  // allocating a few hundred objects sixty times a second, which is a garbage
  // collector pause on a television every few seconds.
  const screen = wire.parts.map((part) => new Float32Array(part.verts.length));

  let frame = 0;
  let width = 0;
  let height = 0;

  const resize = () => {
    // The canvas has two sizes: the box it occupies, and the pixels behind it.
    // Setting only the first gives a wireframe drawn at a quarter resolution on
    // a 4K television and blurred back up to fill it.
    const ratio = window.devicePixelRatio || 1;
    width = element.clientWidth;
    height = element.clientHeight;
    element.width = Math.max(1, Math.round(width * ratio));
    element.height = Math.max(1, Math.round(height * ratio));
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
  };

  const observer = new ResizeObserver(resize);
  observer.observe(element);
  resize();

  const started = performance.now();
  const draw = (now: number) => {
    frame = requestAnimationFrame(draw);
    if (width <= 0 || height <= 0) return;
    const angle = ((now - started) / 1000) * payload.spin * Math.PI * 2;
    const cam = camera(angle, payload.tilt, width, height, bounds);

    context.clearRect(0, 0, width, height);
    context.lineCap = "round";

    // Where the wave has got to. Subtracting the part's own position is what
    // makes it travel: at any instant the model holds the whole ramp spread
    // along it, and a moment later that gradient has moved along by a little.
    const turn = wave ? (now - started) / 1000 / wave.seconds : 0;
    const colours = wire.parts.map((_, at) => {
      if (pinned[at]) return pinned[at] as string;
      if (!wave || phase[at] === null) return ink;
      const { from, to, mix } = rampAt(
        ramp.length,
        turn - (phase[at] as number) * wave.spread,
      );
      return mixed(ramp[from], ramp[to], mix);
    });

    // Every point, once, into the scratch arrays: x and y in pixels and the
    // depth it landed at. Both passes below read these, so a point is never
    // projected twice.
    wire.parts.forEach((part, at) => {
      const out = screen[at];
      const [dx, dy, dz] = moved[at];
      for (let i = 0; i < part.verts.length; i += 3) {
        const p = project(
          part.verts[i] + dx,
          part.verts[i + 1] + dy,
          part.verts[i + 2] + dz,
          cam,
        );
        out[i] = p.sx;
        out[i + 1] = p.sy;
        out[i + 2] = p.depth;
      }
    });

    // Grouped by colour and then by depth, because both are things the canvas
    // has to be told once per group rather than once per line. Parts sharing a
    // colour share their paths, so a model in one colour is still the six
    // strokes it always was, and one whose every part differs is six per
    // colour — against one per edge, which on five thousand edges is the
    // difference between a widget that costs nothing and the most expensive
    // thing on the board.
    //
    // Built fresh every frame rather than kept: a Path2D cannot be emptied, and
    // the points in one are last frame's.
    const groups = new Map<string, Path2D[]>();
    wire.parts.forEach((part, at) => {
      const out = screen[at];
      let bands = groups.get(colours[at]);
      if (!bands) {
        bands = Array.from({ length: BANDS }, () => new Path2D());
        groups.set(colours[at], bands);
      }
      for (let i = 0; i < part.edges.length; i += 2) {
        const a = part.edges[i] * 3;
        const b = part.edges[i + 1] * 3;
        // The band is chosen by the middle of the line, not by either end. An
        // edge running from the back of the model to the front belongs to
        // neither, and picking an end makes which one it is depend on the order
        // the exporter happened to write the face in.
        const band = bandAt((out[a + 2] + out[b + 2]) / 2, cam.reach);
        bands[band].moveTo(out[a], out[a + 1]);
        bands[band].lineTo(out[b], out[b + 1]);
      }
    });

    // The halo under everything first, then the bright lines over all of it —
    // rather than halo-and-line per colour, which would let one part's halo lie
    // on top of another part's lines and dim them.
    const pixel = Math.max(1, Math.min(width, height) / 320);
    for (const wide of [true, false]) {
      context.lineWidth = pixel * (wide ? HALO_WIDTH : 1);
      for (const [colour, bands] of groups) {
        context.strokeStyle = colour;
        bands.forEach((path, band) => {
          context.globalAlpha = bandFade(band) * (wide ? HALO_ALPHA : 1);
          context.stroke(path);
        });
      }
    }
    context.globalAlpha = 1;
  };
  frame = requestAnimationFrame(draw);

  return () => {
    cancelAnimationFrame(frame);
    observer.disconnect();
  };
}
