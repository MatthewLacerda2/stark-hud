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
would pull JAX and a CUDA stack onto a machine whose job is to show a board.

Every number in the shape comes from the model. Nothing is chosen because it
looked better:

  * The **embedding** is a wide lattice, and its radius is the square root of
    its parameter count against one block's — so it is about twice a block's
    width because it genuinely holds about four times the numbers. The same
    lattice is drawn again at the top, because the head is that tensor
    transposed and there is only one of it.
  * Each **block** is a toothed hub inside a wider ring. The teeth are the
    attention heads, and there are as many as the model has; the longer ones
    mark the GQA groups those heads share key and value projections into. The
    ring around it is the MLP, and how far out it sits is the square root of
    the SwiGLU expansion, so a block looks as top-heavy as it actually is.
  * **Seven** of those are the encoder, used once each. The **eighth** is
    larger and solid, because it is the one that runs again and again, and the
    loops threaded through it are the refinement passes — one per step at
    inference depth.

Explode does almost nothing to this object, and that is understood rather than
unnoticed: the widget dilates part centroids and the auto-fit divides by the
grown reach, which cancels for a stack of flat plates with no thickness to
shed. Colour is this object's animation.
"""

import argparse
import ast
import math
import sys
from pathlib import Path

# Run as a script rather than imported as a package member, so the module next
# door is not on the path unless it is put there.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shapes import Obj, band, ticks, torus, tube, web

# Proportions for the instrument, in arbitrary units — the backend centres and
# scales whatever it is given, so only the ratios matter here.
BLOCK_RADIUS = 0.62
ENCODER_GAP = 0.235
CHAMBER_Y = 0.62
SLAB_Y = 1.95
# How round a round thing looks. Past about forty segments the extra edges stop
# reading as curvature on a television and start filling the shape in.
SEGMENTS = 42
SLAB_RINGS = 5
SLAB_SPOKES = 64

# What the shape is built from, and what to fall back on when a config computes
# a value rather than stating it. Every one of these changes the object.
WANTED = {
    "LATENT_DIM": 960,
    "VOCAB_SIZE": 50304,
    "NUM_HEADS": 15,
    "REFINER_ENCODER_LAYERS": 7,
    "INFERENCE_DEPTH": 6,
}


def read_config(path: Path) -> dict[str, int]:
    """The architecture constants, parsed out of ``config.py`` without running it.

    Only plain literal assignments are read. Several of these sit behind an
    ``os.environ.get`` so a run can be chosen at launch, and those fall back to
    the default beside them in ``WANTED`` — which is what the repository ships.
    The alternative is executing a research config to draw a picture of it.
    """
    found = dict(WANTED)
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in WANTED:
                try:
                    value = ast.literal_eval(node.value)
                except ValueError:
                    continue  # An env-overridable knob; the default stands.
                if isinstance(value, int):
                    found[target.id] = value
    return found


def mlp_hidden(dim: int) -> int:
    """The SwiGLU inner width, rounded the way the model rounds it."""
    return ((int(8 * dim / 3) + 63) // 64) * 64


def slab_ratio(dim: int, vocab: int) -> float:
    """How much wider the embedding lattice is drawn than one block.

    The square root of the parameter ratio, because these are areas on a screen
    and a count should read as an area — at a straight ratio the slab is four
    times as wide as a block and swamps the instrument it belongs to.
    """
    block = 4 * dim * dim + 3 * dim * mlp_hidden(dim)
    return math.sqrt((vocab * dim) / block)


def draw_block(obj: Obj, y: float, radius: float, heads: int, groups: int, expand: float) -> None:
    """One transformer block: a toothed attention hub inside its MLP ring.

    The teeth are the heads. They stick out of the rim rather than dividing it,
    because a division is invisible on a circle — fifteen segments in a smooth
    ring is a smooth ring, while fifteen teeth are countable from a sofa. The
    longer ones are the GQA groups: the heads share a smaller number of key and
    value projections, and where those boundaries fall is a fact about the
    block rather than decoration.

    The MLP sits outside as its own ring, at the square root of its expansion.
    Same reasoning as the embedding lattice: a width standing in for an amount
    should read as an area.
    """
    band(obj, y, radius * 0.74, radius, SEGMENTS)
    ticks(obj, y, radius, radius * 1.12, heads, 0.028)
    ticks(obj, y, radius, radius * 1.3, groups, 0.02)
    band(obj, y + 0.055, radius * expand * 0.94, radius * expand, SEGMENTS)


def pass_loop(obj: Obj, y: float, ring: float, azimuth: float) -> None:
    """One refinement pass: a loop threaded through the shared block.

    The loop lies in a vertical plane through the axis, so it dives through the
    middle of the ring and comes back around outside it — a thread through a
    hoop, which is the only honest picture of a block applied to its own
    output. One per step, evenly spaced around the axis.
    """
    cx, cz = math.cos(azimuth), math.sin(azimuth)
    centre = ring / 2
    points = []
    for i in range(SEGMENTS):
        angle = 2 * math.pi * i / SEGMENTS
        out = centre + centre * 1.4 * math.cos(angle)
        points.append((out * cx, y + centre * 0.98 * math.sin(angle), out * cz))
    obj.loop(points)


def build(conf: dict[str, int]) -> Obj:
    """The whole instrument, bottom to top."""
    obj = Obj("TinyRefinementModel — generated by tools/mesh/trm.py")
    dim, layers = conf["LATENT_DIM"], conf["REFINER_ENCODER_LAYERS"]
    depth, heads = conf["INFERENCE_DEPTH"], conf["NUM_HEADS"]
    # Grouped the way the model groups them, and never fewer than one: a very
    # narrow model would otherwise ask for zero ticks.
    groups = max(heads // 4, 1)
    expand = math.sqrt(mlp_hidden(dim) / dim)
    slab = BLOCK_RADIUS * slab_ratio(dim, conf["VOCAB_SIZE"])

    obj.part("embed")
    web(obj, -SLAB_Y, slab, SLAB_RINGS, SLAB_SPOKES)

    # Stacked downward from just below the chamber, so adding a layer grows the
    # instrument toward its embedding instead of shoving the loop upward.
    for i in range(layers):
        obj.part(f"encoder_{i + 1}")
        draw_block(obj, -0.35 - (layers - 1 - i) * ENCODER_GAP, BLOCK_RADIUS, heads, groups, expand)

    # The shared block is the same block drawn larger and given a solid core:
    # it is the one piece of this machine that runs more than once.
    obj.part("refine_block")
    torus(obj, CHAMBER_Y, BLOCK_RADIUS * 1.2, 0.045, SEGMENTS, 6)
    draw_block(obj, CHAMBER_Y, BLOCK_RADIUS * 1.2, heads, groups, expand)

    for k in range(depth):
        obj.part(f"pass_{k + 1}")
        pass_loop(obj, CHAMBER_Y, BLOCK_RADIUS * 1.2, 2 * math.pi * k / depth)

    # Two rings in, one ring out: the gate reads z_new beside z and hands back a
    # blend of the two.
    obj.part("gate")
    band(obj, CHAMBER_Y + 0.62, BLOCK_RADIUS * 0.3, BLOCK_RADIUS * 0.36, SEGMENTS)
    band(obj, CHAMBER_Y + 0.7, BLOCK_RADIUS * 0.3, BLOCK_RADIUS * 0.36, SEGMENTS)
    torus(obj, CHAMBER_Y + 0.78, BLOCK_RADIUS * 0.33, 0.03, SEGMENTS, 5)

    obj.part("head")
    web(obj, SLAB_Y, slab, SLAB_RINGS, SLAB_SPOKES)

    # The residual stream: the one straight line in the object, because
    # everything else here is something done to it.
    obj.part("stream")
    tube(obj, -SLAB_Y, SLAB_Y, 0.013, 5)
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
    target = args.out.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build(conf).text())

    print(
        f"dim {conf['LATENT_DIM']} · vocab {conf['VOCAB_SIZE']} · "
        f"{conf['NUM_HEADS']} heads in {max(conf['NUM_HEADS'] // 4, 1)} groups · "
        f"{conf['REFINER_ENCODER_LAYERS']} encoder blocks · depth {conf['INFERENCE_DEPTH']}"
    )
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
