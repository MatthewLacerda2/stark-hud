/**
 * A prepared model on a canvas: the camera, the clock and the drawing.
 *
 * The other half of `lib/hologram.ts`, which reads a file and makes it into
 * light once. This is what runs for as long as the widget is on the board, and
 * it is the only part that talks to the GPU. A colour change, a new camera
 * angle or a resize reaches only this, so a panel recoloured every few seconds
 * never makes the model be read again.
 */
import {
  AnimationMixer,
  Color,
  Group,
  LinearSRGBColorSpace,
  PerspectiveCamera,
  Scene,
  Vector3,
  WebGLRenderer,
} from "three";
import { HALO_WIDTH, type Prepared } from "@/lib/hologram";
import {
  explodeOffsets,
  FIT,
  fitDistance,
  heading,
  phases,
  rampAt,
  type Vec3,
} from "@/lib/mesh";

/** The upright axis, which the model turns about. */
const UP = new Vector3(0, 1, 0);

/** A colour as the numbers needed to mix it: red, green, blue, 0-255. */
export type Ink = [number, number, number];

/** How the model is to be looked at and coloured. Everything a payload says. */
export type Look = {
  spin: number;
  sweep: number;
  heading: number;
  tilt: number;
  fov: number;
  zoom: number;
  panX: number;
  panY: number;
  explode: number;
  /** The widget's own colour, for anything no rule names. */
  ink: Ink;
  /** Per drawable, the colour a rule pins it to, or null. */
  pinned: (Ink | null)[];
  wave: {
    mode: "stack" | "loop";
    seconds: number;
    spread: number;
    ramp: Ink[];
  } | null;
};

/** Numbers 0-255 as a three.js colour, into one that already exists. */
function paint(target: Color, [r, g, b]: Ink): void {
  target.setRGB(r / 255, g / 255, b / 255);
}

/**
 * A prepared model on a canvas: the camera, the clock and the drawing.
 *
 * It draws only when something moves. A model held still with nothing animated
 * is drawn once per change and then costs nothing, which on a dashboard left up
 * all day is most of the time.
 */
export class View {
  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  private readonly stage = new Group();
  private readonly camera = new PerspectiveCamera();
  private readonly mixer: AnimationMixer | null;
  private readonly model: Prepared;
  private readonly phase: (number | null)[] = [];
  private readonly scratch = new Color();
  private look: Look | null = null;
  private offsets: Vec3[] = [];
  /** What the camera was last fitted for; fitting is not a per-frame job. */
  private fitted = "";
  private width = 0;
  private height = 0;
  private frame = 0;
  private readonly started = performance.now();
  private last = performance.now();

  constructor(canvas: HTMLCanvasElement, model: Prepared) {
    this.model = model;
    this.renderer = new WebGLRenderer({ canvas, alpha: true, antialias: true });
    this.renderer.outputColorSpace = LinearSRGBColorSpace;
    this.renderer.setClearColor(0x000000, 0);
    this.stage.add(model.root);
    this.scene.add(this.stage);
    this.mixer = model.clips.length ? new AnimationMixer(model.root) : null;
    for (const clip of model.clips) this.mixer?.clipAction(clip).play();
  }

  /** The widget changed size: the canvas, the lines and the camera follow. */
  resize(width: number, height: number): void {
    this.width = width;
    this.height = height;
    this.renderer.setPixelRatio(window.devicePixelRatio || 1);
    this.renderer.setSize(width, height, false);
    this.request();
  }

  /** A new way of looking at it. Nothing about the model is read again. */
  set(look: Look): void {
    this.look = look;
    const { model } = this;
    this.offsets = explodeOffsets(model.centers, model.radius, look.explode);
    model.parts.forEach((part, at) => part.position.set(...this.offsets[at]));
    this.phase.length = 0;
    if (look.wave) this.phase.push(...phases(model.centers, look.wave.mode));
    this.request();
  }

  /** Stop drawing and let go of the GPU. */
  dispose(): void {
    cancelAnimationFrame(this.frame);
    this.renderer.dispose();
    this.renderer.forceContextLoss();
  }

  /** Every way the model will face, for fitting it: sampled across a turn. */
  private facings(look: Look): number[] {
    const standing = (look.heading * Math.PI) / 180;
    if (look.spin === 0) return [standing];
    const steps = 16;
    const reach =
      look.sweep > 0 ? (look.sweep * Math.PI) / 180 : Math.PI * (1 - 1 / steps);
    return Array.from(
      { length: steps + 1 },
      (_, i) => standing - reach + (2 * reach * i) / steps,
    );
  }

  /** Whether anything on screen changes with time. */
  private moving(): boolean {
    const look = this.look;
    return Boolean(
      look && (look.spin !== 0 || look.wave !== null || this.mixer !== null),
    );
  }

  private request(): void {
    if (!this.frame)
      this.frame = requestAnimationFrame((now) => this.draw(now));
  }

  private draw(now: number): void {
    this.frame = 0;
    const look = this.look;
    if (!look || this.width <= 0 || this.height <= 0) return;
    const seconds = (now - this.started) / 1000;
    this.mixer?.update(Math.min((now - this.last) / 1000, 0.1));
    this.last = now;

    this.stage.rotation.y =
      (look.heading * Math.PI) / 180 + heading(seconds, look.spin, look.sweep);
    this.colour(look, seconds);
    const { spin, sweep, heading: facing, tilt, fov, zoom, panX, panY } = look;
    const asked = [spin, sweep, facing, tilt, fov, zoom, panX, panY]
      .concat(look.explode, this.width, this.height)
      .join();
    if (asked !== this.fitted) {
      this.frameCamera(look);
      this.fitted = asked;
    }

    const pixel = Math.max(1, Math.min(this.width, this.height) / 560);
    for (const drawable of this.model.drawables) {
      for (const line of drawable.lines) {
        line.resolution.set(this.width, this.height);
        line.linewidth = line.userData.halo ? pixel * HALO_WIDTH : pixel;
      }
      for (const dots of drawable.points) dots.size = pixel * 2;
    }
    this.renderer.render(this.scene, this.camera);
    if (this.moving()) this.request();
  }

  /** Every drawable's colour at this moment: pinned, on the wave, or the ink. */
  private colour(look: Look, seconds: number): void {
    const { wave } = look;
    const turn = wave ? seconds / wave.seconds : 0;
    this.model.drawables.forEach((drawable, at) => {
      const pinned = look.pinned[at];
      const place = this.phase[drawable.part] ?? null;
      if (pinned) paint(this.scratch, pinned);
      else if (wave && place !== null) {
        const { from, to, mix } = rampAt(
          wave.ramp.length,
          turn - place * wave.spread,
        );
        const [a, b] = [wave.ramp[from], wave.ramp[to]];
        paint(this.scratch, [
          a[0] + (b[0] - a[0]) * mix,
          a[1] + (b[1] - a[1]) * mix,
          a[2] + (b[2] - a[2]) * mix,
        ]);
      } else paint(this.scratch, look.ink);
      for (const fill of drawable.fills)
        (fill.uniforms.colour.value as Color).copy(this.scratch);
      for (const line of drawable.lines) line.color.copy(this.scratch);
      for (const dots of drawable.points) dots.color.copy(this.scratch);
    });
  }

  /**
   * Stand the camera back far enough to see the whole model, then zoom and pan.
   *
   * Fitted to what it actually covers: a sample of its own points, projected,
   * at every way it will face — one heading for a model held still, a ring of
   * them for one that turns. A sphere or a box round the model would be simpler
   * and leaves it sitting small in its widget, with the empty corners of a
   * shape it is not drawn around it. Worked out when the view or the widget
   * changes, never per frame.
   */
  private frameCamera(look: Look): void {
    const aspect = this.width / this.height;
    const { camera } = this;
    camera.fov = look.fov;
    camera.aspect = aspect;
    camera.updateProjectionMatrix();

    const tilt = (look.tilt * Math.PI) / 180;
    const toward = new Vector3(0, Math.sin(tilt), Math.cos(tilt));
    const place = (distance: number) => {
      camera.position.copy(toward).multiplyScalar(distance);
      camera.lookAt(0, 0, 0);
      camera.updateMatrixWorld(true);
    };

    const points = this.model.samples.map(({ at, part }) =>
      at.clone().add(new Vector3(...(this.offsets[part] ?? [0, 0, 0]))),
    );
    const seen = this.facings(look).flatMap((angle) =>
      points.map((point) => point.clone().applyAxisAngle(UP, angle)),
    );
    const reach = Math.max(...points.map((point) => point.length()), 1e-6);
    let distance = fitDistance(reach, look.fov, aspect);
    // The picture shrinks roughly as one over the distance, so scaling the
    // distance by how far off the fit it is lands on the fit in a few steps.
    for (let step = 0; step < 5; step++) {
      place(distance);
      const widest = Math.max(
        ...seen.map((point) => {
          const flat = point.clone().project(camera);
          return Math.max(Math.abs(flat.x), Math.abs(flat.y));
        }),
      );
      if (widest <= 0) break;
      distance *= widest / FIT;
    }
    distance /= look.zoom;
    place(distance);

    // Pan slides the camera, not the model, so it moves across the widget by a
    // fraction of what the widget shows at the model's distance.
    const tall = 2 * distance * Math.tan((look.fov * Math.PI) / 360);
    const right = new Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    const up = new Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
    const shift = right
      .multiplyScalar(-look.panX * tall * aspect)
      .add(up.multiplyScalar(-look.panY * tall));
    camera.position.add(shift);
    camera.updateMatrixWorld(true);
  }
}
