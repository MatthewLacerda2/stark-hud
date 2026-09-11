/**
 * Draw a wireframe to an SVG, using the board's own projection and colouring.
 *
 * Not a gate and not a test — a way to look at the thing. The arithmetic in
 * `lib/mesh.ts` has tests saying a near point draws bigger than a far one and
 * that nothing escapes the widget, and all of that can hold while the picture
 * is still wrong in some way nobody thought to assert. This renders the real
 * functions to a file somebody can open.
 *
 *   bun scripts/preview-mesh.mjs model.json out.svg [explode] [tilt] [wave] [ratio]
 *
 * `wave` is "stack" or "loop"; `ratio` is the widget's width over its height,
 * so a model can be checked in the shape of the widget it will actually live
 * in rather than always in a square.
 *
 * The ramp here is written in hex rather than in the board's colour tokens: a
 * token is only a colour once a browser has resolved it against the stylesheet,
 * and there is no browser here. The widget does that resolving for real.
 */
import { readFileSync, writeFileSync } from "node:fs";
import {
  BANDS,
  bandAt,
  bandFade,
  camera,
  layout,
  phases,
  project,
  rampAt,
} from "../src/lib/mesh.ts";

const [source, target, explode = "0", tilt = "16", wave, ratio = "1"] =
  process.argv.slice(2);
const wire = JSON.parse(readFileSync(source, "utf8"));

const HEIGHT = 340;
const WIDTH = Math.round(HEIGHT * Number(ratio));
const ANGLES = [0, 0.125, 0.25, 0.375];
const RAMP = [
  [255, 255, 255],
  [95, 200, 245],
  [232, 106, 90],
];

const { moved, bounds } = layout(wire.parts, Number(explode), Number(tilt));
const phase = wave ? phases(wire.parts, wave) : [];

/** Where a part sits on the ramp at this point in the cycle. */
function colourOf(at, turn) {
  if (!wave || phase[at] === null) return "#8fd8ff";
  const { from, to, mix } = rampAt(RAMP.length, turn - phase[at]);
  const band = (i) =>
    Math.round(RAMP[from][i] + (RAMP[to][i] - RAMP[from][i]) * mix);
  return `rgb(${band(0)} ${band(1)} ${band(2)})`;
}

/** One frame, as the paths for each colour and depth. */
function frame(turn) {
  const cam = camera(turn * Math.PI * 2, Number(tilt), WIDTH, HEIGHT, bounds);
  const groups = new Map();
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
    const colour = colourOf(at, turn);
    if (!groups.has(colour))
      groups.set(
        colour,
        Array.from({ length: BANDS }, () => []),
      );
    const bands = groups.get(colour);
    for (let i = 0; i < part.edges.length; i += 2) {
      const a = points[part.edges[i]];
      const b = points[part.edges[i + 1]];
      bands[bandAt((a.depth + b.depth) / 2, cam.reach)].push(
        `M${a.sx.toFixed(1)} ${a.sy.toFixed(1)}L${b.sx.toFixed(1)} ${b.sy.toFixed(1)}`,
      );
    }
  }
  return groups;
}

const panels = ANGLES.map((turn, column) => {
  const strokes = [];
  for (const wide of [true, false])
    for (const [colour, bands] of frame(turn))
      bands.forEach((path, band) => {
        if (!path.length) return;
        strokes.push(
          `<path d="${path.join("")}" stroke="${colour}" fill="none" ` +
            `stroke-width="${wide ? 3.5 : 1}" stroke-linecap="round" ` +
            `opacity="${(bandFade(band) * (wide ? 0.22 : 1)).toFixed(3)}"/>`,
        );
      });
  return `<g transform="translate(${column * WIDTH} 0)">${strokes.join("")}</g>`;
});

writeFileSync(
  target,
  `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH * ANGLES.length}" height="${HEIGHT}">` +
    `<rect width="100%" height="100%" fill="#0a0e14"/>${panels.join("")}</svg>`,
);
console.log(
  `${target}  parts=${wire.parts.length} ` +
    `radial=${bounds.radial.toFixed(3)} vertical=${bounds.vertical.toFixed(3)}`,
);
