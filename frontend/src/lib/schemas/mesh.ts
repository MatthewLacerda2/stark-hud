/**
 * What a mesh widget shows, mirroring `backend/schemas/mesh.py`.
 *
 * Its own module for the reason the flow's models have one: a payload made of
 * three further models is not one more block of fields, and `board.ts` is at
 * the house's 550-line ceiling. `board.ts` re-exports it, so nothing has to
 * know.
 */

/**
 * A 3D model drawn as a hologram, from a model file on the host.
 *
 * The path is here and the model is not: the file itself comes from
 * `/api/v1/mesh/{id}` when the widget mounts, the same way a picture's bytes
 * come from `/api/v1/media/{id}`, and three.js reads it in the browser.
 */
export interface MeshPayload {
  kind: "mesh";
  /** A .glb, .gltf, .fbx or .obj on the machine running the board. */
  path: string;
  /** Turns per second about the upright axis; 0 holds it still. */
  spin: number;
  /** Degrees each way to swing instead of going round; 0 keeps turning. */
  sweep: number;
  /** Where it stands, degrees counter-clockwise seen from above. */
  heading: number;
  /** How far above the model the camera sits, in degrees. */
  tilt: number;
  /** The camera's field of view, in degrees. */
  fov: number;
  /** How big it is drawn against the size that just fits; above 1 crops in. */
  zoom: number;
  /** Where it sits across the widget, as a fraction of its width. */
  pan_x: number;
  /** Where it sits up the widget, as a fraction of its height. */
  pan_y: number;
  /** 0 assembled, 1 a full model-width of separation between the parts. */
  explode: number;
  /**
   * A colour per part, keyed by its name in the file. Keys may be globs, and
   * the longest matching pattern wins. A rule on a node covers what is inside
   * it. A part named here keeps this colour and does not take the wave.
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
