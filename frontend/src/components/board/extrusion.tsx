import { useEffect, useRef, type ReactNode } from "react";
import { farther } from "@/lib/depth";

/**
 * How many copies lay a chart's marks down into the pane.
 *
 * Enough that neighbouring copies stay about a pixel apart when the board leans
 * hard, so the side is a surface rather than a stack of outlines, and few enough
 * that the copies of a gauge are still nothing to paint.
 */
const LAYERS = 8;

/**
 * How deep the marks go, in panes.
 *
 * Deeper than the glass they sit in, deliberately. At the pane's own thickness
 * the sides of a gauge were four pixels at the bottom of the board and nothing
 * at all in its middle — correct, and invisible from a sofa. The walls are a
 * cue; the marks are the thing being looked at, so they are allowed to be more.
 * Two and a half panes was too strong on the board and half of that too weak;
 * the board owner settled between them.
 */
const PANES = 1.75;

/**
 * How much light the side catches right behind the face, and at the back.
 *
 * Brightness, not opacity, and that is the difference between a solid and a
 * glow. The first version faded the copies out instead, and a white mark going
 * see-through over a dark room is exactly what light spilling off it looks
 * like: the charts read as made of light. A solid's sides are the same material
 * in less light — opaque, darker, and darker still further in — so the face
 * meets its side at a hard edge rather than a haze.
 */
const LIT_NEAR = 0.6;
// Nearly dark at the back. A side lit evenly across its depth reads as a flat
// copy of the mark, which is what the first opaque version looked like.
const LIT_FAR = 0.2;

/**
 * A chart with a thickness: its marks copied back into the pane behind it.
 *
 * The chart itself is untouched and stays on the face. Behind it, `LAYERS`
 * copies of the whole widget are cloned from the page — not rendered again,
 * which would be five more charts measuring themselves and animating — and the
 * stylesheet shows only the marks in them (`extrude-copy`), each set a little
 * deeper and in a little less light. Clones keep the marks' own colours, which a drop
 * shadow cannot: a red bar has red sides.
 *
 * The copies follow the chart. A MutationObserver re-clones whenever the chart
 * changes, at most once a frame, so a gauge that moves or animates in carries
 * its sides with it.
 *
 * Off a depth board this draws the chart and nothing else: there is no pane for
 * the marks to run back into.
 */
export function Extrusion({ children }: { children: ReactNode }) {
  const front = useRef<HTMLDivElement>(null);
  const back = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const source = front.current;
    const target = back.current;
    if (!source || !target || !source.closest(".depth-board")) return;

    let frame = 0;
    const copy = () => {
      frame = 0;
      const layers = Array.from({ length: LAYERS }, (_, at) => {
        // Deepest first, so each nearer copy paints over the one behind it.
        const depth = (LAYERS - at) / LAYERS;
        const layer = document.createElement("div");
        layer.className = "extrude-copy";
        layer.style.setProperty(
          "--extrude-at",
          `calc(var(--slab, 0px) * ${PANES * depth})`,
        );
        layer.style.setProperty(
          "--extrude-scale",
          String(farther(PANES * depth, window.innerWidth, window.innerHeight)),
        );
        layer.style.filter = `brightness(${LIT_NEAR + (LIT_FAR - LIT_NEAR) * depth})`;
        for (const node of source.childNodes)
          layer.append(node.cloneNode(true));
        return layer;
      });
      target.replaceChildren(...layers);
    };
    const soon = () => {
      if (!frame) frame = requestAnimationFrame(copy);
    };

    const observer = new MutationObserver(soon);
    observer.observe(source, {
      subtree: true,
      childList: true,
      attributes: true,
      characterData: true,
    });
    soon();
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      target.replaceChildren();
    };
  }, []);

  return (
    // Its own stacking context, so the copies can sit behind the chart without
    // falling behind the widget's pane.
    <div className="relative isolate size-full">
      <div ref={back} aria-hidden className="absolute inset-0 -z-10" />
      <div ref={front} className="size-full">
        {children}
      </div>
    </div>
  );
}
