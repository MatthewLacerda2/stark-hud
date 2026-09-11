#!/usr/bin/env python3
"""Build the TinyRefinementModel's architecture as an object the board can draw.

    python tools/mesh/trm.py ~/Desktop/Repos/TinyRefinementModel -o state/models/trm.obj

Generated rather than modelled, and that is the whole point. The model this
draws is being actively worked on; a shape built by hand in Blender would be a
picture of the architecture on the day somebody drew it, and every change would
mean drawing it again. This reads the real constants out of ``trm/config.py``
and emits the object, so widening the model or adding an encoder layer is a
re-run rather than a modelling session.

The constants are read with ``ast``, never imported. Importing ``trm.config``
would pull in JAX and a CUDA stack to learn seven integers, and this has to run
on a machine that only shows the board.

Nothing here needs Blender either. Every part is a ring, a disc or a loop —
shapes that are three lines of trigonometry each — so this writes the OBJ
directly and the whole pipeline is the standard library.

What the shape is saying, from the bottom up:

  * The **embedding** is a wide flat web, and its radius is not a taste
    decision — it is proportional to the square root of its parameter count
    against one block's, so the slab is about twice a block's width because it
    genuinely holds about four times the numbers. The same web appears at the
    top as the **head**, because it is the same tensor doing a second job.
  * The **seven encoder rings** are seven separate parts, each used once.
  * The **refine ring** is one part, and the **passes** are loops threaded
    through it — one loop per refinement step. Assembled, they read as what the
    model does: a single block with the state going round it again and again.
    Exploded, they fan apart into K separate stages, which is the same thing
    unrolled. The widget's explode dial moves between those two readings, and
    that is the one animation this object really wants.
"""

import argparse
import ast
import math
from pathlib import Path

Point = tuple[float, float, float]

# The board's own proportions for the instrument, in arbitrary units — the
# backend centres and scales whatever it is given, so only the ratios matter.
BLOCK_RADIUS = 0.72
RING_TUBE = 0.05
ENCODER_GAP = 0.2
CHAMBER_Y = 0.45
SLAB_Y = 1.8
# How round things look. A wireframe on a television stops reading as curvature
# and starts filling in somewhere around two dozen segments a circle.
SEGMENTS = 28
SLAB_RINGS = 4
SLAB_SPOKES = 36

# The constants this shape is built from, and the value to fall back on when a
# config does not name one. Every one of them changes the object.
WANTED = {
    "LATENT_DIM": 960,
    "VOCAB_SIZE": 50304,
    "REFINER_ENCODER_LAYERS": 7,
    "INFERENCE_DEPTH": 6,
}


def read_config(path: Path) -> dict[str, int]:
    """The architecture constants, parsed out of ``config.py`` without running it.

    Only plain literal assignments are read. Anything computed — and several of
    these are, behind an ``os.environ.get`` so a run can be chosen at launch —
    falls back to the default beside it in ``WANTED``, which is what the
    repository ships. The alternative is executing a research config to draw a
    picture of it, and that pulls in JAX.
    """
    found = dict(WANTED)
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id not in WANTED:
                continue
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                continue  # An env-overridable knob; the default already stands.
            if isinstance(value, int):
                found[target.id] = value
    return found


def slab_ratio(dim: int, vocab: int) -> float:
    """How much wider the embedding slab is drawn than one block's ring.

    The square root of the parameter ratio, because these are areas on the
    screen and a count should read as an area rather than as a length —
    otherwise the slab is four times as wide as a block and swamps the whole
    instrument. A SwiGLU block is four square projections plus three of
    dim by hidden, and hidden is the same multiple-of-64 rounding the model uses.
    """
    hidden = ((int(8 * dim / 3) + 63) // 64) * 64
    block = 4 * dim * dim + 3 * dim * hidden
    return math.sqrt((vocab * dim) / block)


class Obj:
    """An OBJ file being written: named parts, points, faces and open curves."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.count = 0

    def part(self, name: str) -> None:
        """Start a new named object. This is what the widget explodes."""
        self.lines.append(f"o {name}")

    def add(self, points: list[Point]) -> int:
        """Write points, and hand back the 1-based index of the first."""
        base = self.count + 1
        for x, y, z in points:
            self.lines.append(f"v {x:.5f} {y:.5f} {z:.5f}")
        self.count += len(points)
        return base

    def quads(self, base: int, rows: int, cols: int, wrap: bool) -> None:
        """Join a rows by cols lattice of points into faces.

        ``wrap`` closes the lattice around the last column, which is what makes
        a strip of points into a ring rather than a fence.
        """
        for r in range(rows - 1):
            for c in range(cols if wrap else cols - 1):
                nxt = (c + 1) % cols
                corners = [
                    base + r * cols + c,
                    base + r * cols + nxt,
                    base + (r + 1) * cols + nxt,
                    base + (r + 1) * cols + c,
                ]
                self.lines.append("f " + " ".join(str(i) for i in corners))

    def loop(self, points: list[Point]) -> None:
        """A closed curve, written as an OBJ polyline.

        A curve rather than a surface because that is what it is: the path the
        state takes is a thread, and giving it a tube would make it look like
        another component of the machine instead of the thing moving through it.
        """
        base = self.add(points)
        order = [base + i for i in range(len(points))] + [base]
        self.lines.append("l " + " ".join(str(i) for i in order))

    def text(self) -> str:
        """The finished file."""
        return "\n".join(
            ["# TinyRefinementModel — generated by tools/mesh/trm.py", *self.lines, ""]
        )


def disc(obj: Obj, name: str, y: float, radius: float) -> None:
    """A flat polar web: the embedding, and the head that shares its weights.

    Drawn as a lattice rather than an outline so it reads as something dense and
    enormous — which, at 48 million numbers, it is. Both slabs are identical on
    purpose: the head is this tensor transposed, and two identical webs at
    either end of the instrument say so without a label.
    """
    obj.part(name)
    points: list[Point] = []
    for r in range(SLAB_RINGS + 1):
        rr = radius * (r + 1) / (SLAB_RINGS + 1)
        for s in range(SLAB_SPOKES):
            angle = 2 * math.pi * s / SLAB_SPOKES
            points.append((rr * math.cos(angle), y, rr * math.sin(angle)))
    base = obj.add(points)
    obj.quads(base, SLAB_RINGS + 1, SLAB_SPOKES, wrap=True)


def annulus(obj: Obj, name: str, y: float, radius: float, width: float) -> None:
    """A flat ring: one encoder block, used once and never again."""
    obj.part(name)
    points: list[Point] = []
    for rr in (radius - width, radius):
        for s in range(SEGMENTS):
            angle = 2 * math.pi * s / SEGMENTS
            points.append((rr * math.cos(angle), y, rr * math.sin(angle)))
    base = obj.add(points)
    obj.quads(base, 2, SEGMENTS, wrap=True)


def torus(obj: Obj, name: str, y: float, radius: float, tube: float, minor: int = 6) -> None:
    """A solid ring: the one block the loop runs through."""
    obj.part(name)
    points: list[Point] = []
    for i in range(SEGMENTS):
        major = 2 * math.pi * i / SEGMENTS
        cx, cz = math.cos(major), math.sin(major)
        for j in range(minor):
            small = 2 * math.pi * j / minor
            rr = radius + tube * math.cos(small)
            points.append((rr * cx, y + tube * math.sin(small), rr * cz))
    base = obj.add(points)
    obj.quads(base, SEGMENTS, minor, wrap=True)
    # The lattice wraps in the minor direction above; this closes the major one,
    # joining the last cross-section back to the first.
    for j in range(minor):
        nxt = (j + 1) % minor
        obj.lines.append(
            "f "
            + " ".join(
                str(i)
                for i in (
                    base + (SEGMENTS - 1) * minor + j,
                    base + (SEGMENTS - 1) * minor + nxt,
                    base + nxt,
                    base + j,
                )
            )
        )


def pass_loop(obj: Obj, name: str, y: float, ring: float, azimuth: float) -> None:
    """One refinement pass: a loop threaded through the shared ring.

    The loop lies in a vertical plane through the axis, so it dives through the
    middle of the ring and comes back around outside it — a thread through a
    hoop, which is the only honest picture of a block applied to its own output.
    K of them at even azimuths make the rosette; the widget's explode opens them
    outward, and the loop becomes the same computation unrolled into K stages.
    """
    obj.part(name)
    cx, cz = math.cos(azimuth), math.sin(azimuth)
    centre = ring / 2
    points: list[Point] = []
    for i in range(SEGMENTS):
        angle = 2 * math.pi * i / SEGMENTS
        out = centre + centre * 1.35 * math.cos(angle)
        points.append((out * cx, y + centre * 0.95 * math.sin(angle), out * cz))
    obj.loop(points)


def build(conf: dict[str, int]) -> Obj:
    """The whole instrument, bottom to top."""
    obj = Obj()
    layers = conf["REFINER_ENCODER_LAYERS"]
    depth = conf["INFERENCE_DEPTH"]
    slab = BLOCK_RADIUS * slab_ratio(conf["LATENT_DIM"], conf["VOCAB_SIZE"])

    disc(obj, "embed", -SLAB_Y, slab)
    # Stacked downward from just under the chamber, so adding a layer grows the
    # instrument toward its embedding rather than shoving the loop upward.
    for i in range(layers):
        y = -0.4 - (layers - 1 - i) * ENCODER_GAP
        annulus(obj, f"encoder_{i + 1}", y, BLOCK_RADIUS, RING_TUBE * 2.6)

    torus(obj, "refine_block", CHAMBER_Y, BLOCK_RADIUS * 1.15, RING_TUBE * 1.5)
    for k in range(depth):
        pass_loop(obj, f"pass_{k + 1}", CHAMBER_Y, BLOCK_RADIUS * 1.15, 2 * math.pi * k / depth)

    torus(obj, "gate", CHAMBER_Y + 0.75, BLOCK_RADIUS * 0.42, RING_TUBE, minor=5)
    disc(obj, "head", SLAB_Y, slab)

    # The residual stream, as the one straight line in the object: everything
    # else is something done to it.
    obj.part("stream")
    obj.loop([(0.0, -SLAB_Y, 0.0), (0.0, SLAB_Y, 0.0)])
    return obj


def main() -> int:
    """Read a TinyRefinementModel checkout, write the object, say what it built."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", type=Path, help="a TinyRefinementModel checkout")
    parser.add_argument("-o", "--out", type=Path, default=Path("state/models/trm.obj"))
    args = parser.parse_args()

    config = args.repo.expanduser().resolve() / "trm" / "config.py"
    if not config.is_file():
        print(f"No trm/config.py under {args.repo} — is that the repository root?")
        return 1

    conf = read_config(config)
    obj = build(conf)
    target = args.out.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(obj.text())

    print(
        f"dim {conf['LATENT_DIM']} · vocab {conf['VOCAB_SIZE']} · "
        f"{conf['REFINER_ENCODER_LAYERS']} encoder blocks · depth {conf['INFERENCE_DEPTH']}"
    )
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
