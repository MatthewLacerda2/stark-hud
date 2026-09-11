/**
 * Draw a wireframe to an SVG, using the board's own projection.
 *
 * Not a gate and not a test — a way to look at the thing. The arithmetic in
 * `lib/mesh.ts` has tests saying a near point draws bigger than a far one and
 * that nothing escapes the widget, and all of that can hold while the picture
 * is still wrong in some way nobody thought to assert. This renders the real
 * functions to a file somebody can open.
 *
 *   bun frontend/scripts/preview-mesh.mjs reactor.json out.svg [explode] [tilt]
 *
 * The SVG mirrors what the canvas does — the same depth bands, the same two
 * passes for the glow — so what comes out here is what goes on the television,
 * give or take a line cap.
 */
import { readFileSync, writeFileSync } from "node:fs";
import {
  BANDS,
  bandAt,
  bandFade,
  camera,
  layout,
  project,
} from "../src/lib/mesh.ts";

const [source, target, explode = "0", tilt = "16"] = process.argv.slice(2);
const wire = JSON.parse(readFileSync(source, "utf8"));

const SIZE = 300;
const ANGLES = [0, 0.125, 0.25, 0.375];

const { moved, reach } = layout(wire.parts, Number(explode));

/** One turn of the model, as the SVG paths for each depth band. */
function frame(turn) {
  const cam = camera(turn * Math.PI * 2, Number(tilt), SIZE, SIZE, reach);
  const bands = Array.from({ length: BANDS }, () => []);
  for (const [at, part] of wire.parts.entries()) {
    const [dx, dy, dz] = moved[at];
    const points = [];
    for (let i = 0; i < part.verts.length; i += 3)
      points.push(
        project(
          part.verts[i] + dx,
          part.verts[i + 1] + dy,
          part.verts[i + 2] + dz,
          cam,
        ),
      );
    for (let i = 0; i < part.edges.length; i += 2) {
      const a = points[part.edges[i]];
      const b = points[part.edges[i + 1]];
      bands[bandAt((a.depth + b.depth) / 2, cam.reach)].push(
        `M${a.sx.toFixed(1)} ${a.sy.toFixed(1)}L${b.sx.toFixed(1)} ${b.sy.toFixed(1)}`,
      );
    }
  }
  return bands;
}

const panels = ANGLES.map((turn, column) => {
  const bands = frame(turn);
  const strokes = [];
  for (const wide of [true, false])
    bands.forEach((path, band) => {
      if (!path.length) return;
      strokes.push(
        `<path d="${path.join("")}" stroke="#8fd8ff" fill="none" ` +
          `stroke-width="${wide ? 3.5 : 1}" stroke-linecap="round" ` +
          `opacity="${(bandFade(band) * (wide ? 0.22 : 1)).toFixed(3)}"/>`,
      );
    });
  return `<g transform="translate(${column * SIZE} 0)">${strokes.join("")}</g>`;
});

writeFileSync(
  target,
  `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE * ANGLES.length}" height="${SIZE}">` +
    `<rect width="100%" height="100%" fill="#0a0e14"/>${panels.join("")}</svg>`,
);
console.log(`${target}  parts=${wire.parts.length} reach=${reach.toFixed(3)}`);
