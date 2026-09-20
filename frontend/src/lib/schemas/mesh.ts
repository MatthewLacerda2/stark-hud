/**
 * What a mesh widget shows, mirroring `backend/schemas/mesh.py`.
 *
 * Its own module for the reason the flow's models have one: a payload made of
 * three further models is not one more block of fields, and `board.ts` is at
 * the house's 550-line ceiling. `board.ts` re-exports it, so nothing has to
 * know.
 */

/**
 * A 3D model drawn as a turning wireframe.
 *
 * The path is here and the geometry is not: the points and lines come from
 * `/api/v1/mesh/{id}` when the widget mounts, the same way a picture's bytes
 * come from `/api/v1/media/{id}`. A reactor is a few hundred vertices and a
 * downloaded model a hundred thousand, and none of that belongs in a board file
 * a person is meant to be able to open.
 */
export interface MeshPayload {
  kind: "mesh";
  path: string;
  /** Turns per second about the upright axis. Negative goes the other way. */
  spin: number;
  /** Degrees each way to swing instead of going round; 0 keeps turning. */
  sweep: number;
  /** How far above the model the camera sits, in degrees. */
  tilt: number;
  /** 0 assembled, 1 a full model-width of separation between the parts. */
  explode: number;
  /**
   * A colour per part, keyed by its name in the file. Keys may be globs, and
   * the longest matching pattern wins. A part named here keeps this colour and
   * does not take the wave.
   */
  colors: Record<string, string> | null;
  /** A colour running through the model, over and over, or null for none. */
  wave: MeshWave | null;
}

/** A colour travelling through a model: which way, how fast, and through what. */
export interface MeshWave {
  /** Up the model bottom to top, or around its upright axis. */
  mode: "stack" | "loop";
  /** How long one full pass takes. */
  seconds: number;
  /** The ramp, in order. It wraps: the last colour leads back to the first. */
  colors: string[];
  /** How much of the ramp the model holds at once. Above 1 the ramp repeats. */
  spread: number;
}

/** One named object out of the file: points, and the lines between them. */
export interface MeshPart {
  name: string;
  /** x, y, z, x, y, z, … normalised into a unit cube centred on the origin. */
  verts: number[];
  /** Index pairs into `verts`, counted in points rather than in floats. */
  edges: number[];
  /** This part's middle, and so the direction it travels when exploded. */
  center: number[];
}

/** A whole model as the board draws it. Never stored; fetched per widget. */
export interface Wireframe {
  parts: MeshPart[];
  /** What the model measured before normalising, in the file's own units. */
  source_size: number[];
}
