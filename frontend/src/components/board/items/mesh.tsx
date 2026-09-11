import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { MeshPayload, Wireframe } from "@/lib/schemas/board";
import { ApiError } from "@/lib/api/client";
import { getWireframe } from "@/lib/api/mesh";
import { BANDS, bandAt, bandFade, camera, layout, project } from "@/lib/mesh";

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
      <div className="flex size-full flex-col items-center justify-center gap-2 rounded-xl bg-background p-4">
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

  const { moved, reach } = layout(wire.parts, payload.explode);
  const ink = getComputedStyle(element).color;
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
    const cam = camera(angle, payload.tilt, width, height, reach);

    context.clearRect(0, 0, width, height);
    context.lineCap = "round";
    context.strokeStyle = ink;

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

    // Built fresh rather than kept: a Path2D cannot be emptied, and the points
    // in it are last frame's.
    const bands = Array.from({ length: BANDS }, () => new Path2D());
    wire.parts.forEach((part, at) => {
      const out = screen[at];
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

    // Far bands first, so the near side of the model is laid over the far side
    // rather than under it.
    const pixel = Math.max(1, Math.min(width, height) / 320);
    for (const wide of [true, false]) {
      context.lineWidth = pixel * (wide ? HALO_WIDTH : 1);
      bands.forEach((path, band) => {
        context.globalAlpha = bandFade(band) * (wide ? HALO_ALPHA : 1);
        context.stroke(path);
      });
    }
    context.globalAlpha = 1;
  };
  frame = requestAnimationFrame(draw);

  return () => {
    cancelAnimationFrame(frame);
    observer.disconnect();
  };
}
