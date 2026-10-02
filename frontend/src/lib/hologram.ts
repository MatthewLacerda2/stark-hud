/**
 * A model file, made into light: the reading half of the mesh widget.
 *
 * Two steps, split by what they cost and how often they happen. `prepare`, here,
 * reads the file and turns every surface into the board's look — once per file,
 * since that is geometry work. `View`, in `lib/hologram-view.ts`, puts a
 * prepared model on a canvas and keeps it drawn.
 *
 * The look is light, not glass. Every surface is a faint fill that brightens
 * toward its outline (a fresnel rim — that is what gives a flat drawing its
 * volume), and every sharp edge is a glowing line: a wide faint pass under a
 * thin bright one. All of it is added onto what is behind it rather than
 * blended over it. That is how a hologram is lit, and it is also why nothing
 * here has to be sorted: adding is the same in any order, where see-through
 * "glass" has to be drawn back to front and flickers wherever parts sit inside
 * other parts.
 *
 * Nothing fakes depth inside the widget — the model is drawn cleanly onto it:
 * no dimming with distance, no blur, no sway of its own.
 */
import {
  AdditiveBlending,
  Box3,
  BufferGeometry,
  Color,
  ColorManagement,
  DoubleSide,
  EdgesGeometry,
  Group,
  Line,
  LineSegments,
  Mesh,
  type AnimationClip,
  type Material,
  type Object3D,
  Points,
  PointsMaterial,
  ShaderMaterial,
  Sphere,
  Vector3,
} from "three";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry.js";
import { type ModelFormat, type Vec3 } from "@/lib/mesh";
import { labelOf } from "@/lib/mesh-labels";

// Colours arrive as the CSS colours the board resolved them to, and must land
// on the screen as exactly those. three.js otherwise converts them into linear
// light and back, which is right for lighting and wrong for a drawing with no
// lights in it: a board colour would come out a shade off from the same colour
// on the widget beside it.
ColorManagement.enabled = false;

/** An edge is drawn where two faces meet at more than this, in degrees. */
const CREASE = 25;

/** The wide faint pass and the thin bright one, against one line's width. */
export const HALO_WIDTH = 3.5;
const HALO_ALPHA = 0.14;

/** The fill: how much a face glows looking straight at it, and at its rim. */
const FILL_BASE = 0.025;
const FILL_RIM = 0.22;

/** One thing drawn, and every material that has to take its colour. */
export type Drawable = {
  /** Its own name and every name above it, nearest first. */
  names: string[];
  /** Which part it belongs to: a child of the model's root. */
  part: number;
  fills: ShaderMaterial[];
  lines: LineMaterial[];
  points: PointsMaterial[];
};

/** A model read and made into light, ready for any number of views. */
export type Prepared = {
  /** Everything, centred on the origin. */
  root: Group;
  /** The wrapper around each part, which is what explode moves. */
  parts: Group[];
  /** Where each part's middle is, in the centred model. */
  centers: Vec3[];
  radius: number;
  /**
   * A sample of the model's own points, in the centred model, and which part
   * each belongs to: what the camera is fitted to.
   */
  samples: { at: Vector3; part: number }[];
  drawables: Drawable[];
  clips: AnimationClip[];
  /**
   * Every node the file gave a label, in the file's order, and the words. The
   * node itself rather than where it was: it is what an animation, a spin and
   * explode move, so where it is drawn is asked of it each frame.
   */
  labels: { text: string; anchor: Object3D }[];
};

/** Read a model file into an object three.js can draw, and its animations. */
async function read(
  bytes: ArrayBuffer,
  format: ModelFormat,
): Promise<{ root: Object3D; clips: AnimationClip[] }> {
  if (format === "gltf") {
    const gltf = await new GLTFLoader().parseAsync(bytes, "");
    return { root: gltf.scene, clips: gltf.animations };
  }
  if (format === "obj") {
    return {
      root: new OBJLoader().parse(new TextDecoder().decode(bytes)),
      clips: [],
    };
  }
  const root = new FBXLoader().parse(bytes, "");
  return { root, clips: root.animations };
}

/** The fill: faint face-on, brighter toward the outline, added to the scene. */
function fillMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: {
      colour: { value: new Color(1, 1, 1) },
      base: { value: FILL_BASE },
      rim: { value: FILL_RIM },
    },
    vertexShader: `
      varying vec3 vNormal;
      varying vec3 vView;
      void main() {
        vec4 seen = modelViewMatrix * vec4(position, 1.0);
        vNormal = normalize(normalMatrix * normal);
        vView = normalize(-seen.xyz);
        gl_Position = projectionMatrix * seen;
      }`,
    fragmentShader: `
      uniform vec3 colour;
      uniform float base;
      uniform float rim;
      varying vec3 vNormal;
      varying vec3 vView;
      void main() {
        float facing = abs(dot(normalize(vNormal), normalize(vView)));
        gl_FragColor = vec4(colour, base + rim * pow(1.0 - facing, 2.0));
      }`,
    transparent: true,
    blending: AdditiveBlending,
    depthWrite: false,
    side: DoubleSide,
  });
}

/** One pass of glowing line. Its width is set per view, since it is in pixels. */
function lineMaterial(halo: boolean): LineMaterial {
  const material = new LineMaterial({
    transparent: true,
    opacity: halo ? HALO_ALPHA : 1,
    blending: AdditiveBlending,
    depthWrite: false,
    worldUnits: false,
  });
  material.userData.halo = halo;
  return material;
}

/** Pairs of points, out of whatever kind of line three.js read the file as. */
function segmentsOf(line: Line): Float32Array {
  const flat = line.geometry.index
    ? line.geometry.toNonIndexed()
    : line.geometry;
  const points = flat.getAttribute("position").array as ArrayLike<number>;
  if (line instanceof LineSegments) return Float32Array.from(points);
  // A strip: every point is the end of one segment and the start of the next.
  const out: number[] = [];
  for (let i = 3; i < points.length; i += 3)
    for (let k = -3; k < 3; k++) out.push(points[i + k]);
  return Float32Array.from(out);
}

/** Hang the two glowing passes of these segments off an object. */
function glow(owner: Object3D, segments: Float32Array, into: Drawable): void {
  const geometry = new LineSegmentsGeometry().setPositions(segments);
  for (const halo of [true, false]) {
    const material = lineMaterial(halo);
    const drawn = new LineSegments2(geometry, material);
    // Halo under core, whatever order the scene lists them in.
    drawn.renderOrder = halo ? 0 : 1;
    owner.add(drawn);
    into.lines.push(material);
  }
}

/** Every name from this object up to the model's root, nearest first. */
function namesUp(object: Object3D, root: Object3D): string[] {
  const names: string[] = [];
  for (let at: Object3D | null = object; at && at !== root; at = at.parent)
    if (at.name) names.push(at.name);
  return names;
}

/**
 * Read a model file and make it into light, once.
 *
 * Every mesh keeps its geometry and its place in the file's hierarchy — that is
 * what its animation moves — and gets the fill in place of its material, with
 * its sharp edges hung off it as glowing lines. Lines in the file stay lines,
 * and points stay points.
 *
 * Each child of the file's root becomes a part, wrapped in a group of its own:
 * explode moves the wrapper, so it never fights an animation moving the part.
 */
export async function prepare(
  bytes: ArrayBuffer,
  format: ModelFormat,
): Promise<Prepared> {
  const { root: file, clips } = await read(bytes, format);

  const parts = [...file.children].map((child) => {
    const wrap = new Group();
    wrap.add(child);
    file.add(wrap);
    return wrap;
  });
  const partOf = (object: Object3D) => {
    let at: Object3D | null = object;
    while (at && at.parent !== file) at = at.parent;
    return at ? parts.indexOf(at as Group) : 0;
  };

  const found: Object3D[] = [];
  file.traverse((object) => found.push(object));
  const labels = found.flatMap((anchor) => {
    const text = labelOf(anchor.userData);
    return text === null ? [] : [{ text, anchor }];
  });
  const drawables: Drawable[] = [];
  for (const object of found) {
    const drawable: Drawable = {
      names: namesUp(object, file),
      part: partOf(object),
      fills: [],
      lines: [],
      points: [],
    };
    if (object instanceof Mesh) {
      const geometry = object.geometry as BufferGeometry;
      if (!geometry.getAttribute("normal")) geometry.computeVertexNormals();
      const fill = fillMaterial();
      object.material = fill;
      drawable.fills.push(fill);
      const edges = new EdgesGeometry(geometry, CREASE);
      glow(
        object,
        edges.getAttribute("position").array as Float32Array,
        drawable,
      );
    } else if (object instanceof Line) {
      glow(object, segmentsOf(object), drawable);
      (object.material as Material).visible = false;
    } else if (object instanceof Points) {
      const dots = new PointsMaterial({
        size: 2,
        sizeAttenuation: false,
        transparent: true,
        blending: AdditiveBlending,
        depthWrite: false,
      });
      object.material = dots;
      drawable.points.push(dots);
    } else continue;
    drawables.push(drawable);
  }

  const root = new Group();
  root.add(file);
  root.updateMatrixWorld(true);
  const box = new Box3().setFromObject(root);
  const middle = box.getCenter(new Vector3());
  file.position.sub(middle);
  root.updateMatrixWorld(true);
  const radius = box.getBoundingSphere(new Sphere()).radius || 1;
  const centers = parts.map((part) => {
    const c = new Box3().setFromObject(part).getCenter(new Vector3());
    return [c.x, c.y, c.z] as Vec3;
  });
  return {
    root,
    parts,
    centers,
    radius,
    samples: sample(root, partOf),
    drawables,
    clips,
    labels,
  };
}

/** At most this many of a model's points are used to fit the camera. */
const SAMPLES = 1500;

/**
 * An even sample of the points the model is made of, where they sit now.
 *
 * The glowing lines hung off each mesh are left out: they are drawn from the
 * mesh's own points, and their geometry is a unit quad that is not where
 * anything is.
 */
function sample(
  root: Object3D,
  partOf: (object: Object3D) => number,
): { at: Vector3; part: number }[] {
  const sources: { object: Object3D; count: number }[] = [];
  root.traverse((object) => {
    if (object instanceof LineSegments2) return;
    const position = (object as Mesh).geometry?.getAttribute?.("position");
    if (position) sources.push({ object, count: position.count });
  });
  const total = sources.reduce((sum, { count }) => sum + count, 0);
  const stride = Math.max(1, Math.ceil(total / SAMPLES));
  const out: { at: Vector3; part: number }[] = [];
  for (const { object, count } of sources) {
    const position = (object as Mesh).geometry.getAttribute("position");
    const part = partOf(object);
    for (let i = 0; i < count; i += stride)
      out.push({
        at: new Vector3()
          .fromBufferAttribute(position, i)
          .applyMatrix4(object.matrixWorld),
        part,
      });
  }
  return out;
}
