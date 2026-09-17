#!/usr/bin/env python3
"""Build the TinyRefinementModel's architecture as an object the board can draw.

    python tools/mesh/trm.py ~/Desktop/Repos/TinyRefinementModel -o state/models/trm.obj

Generated rather than modelled, and that is the whole point. The model this
draws is being actively worked on; a shape built by hand in Blender would be a
picture of the architecture on the day somebody drew it, and every change would
mean drawing it again. This reads the real constants out of ``trm/config.py``
and emits the object, so widening the model or adding a layer is a re-run
rather than a modelling session.

The constants are read with ``ast``, never imported. Importing ``trm.config``
would pull JAX and a CUDA stack onto a machine whose job is to show a board.

The picture is the one every transformer diagram draws, stood up in three
dimensions. Left to right is the **sequence**; bottom to top is the **forward
pass**. From the sofa it should read, in one look, as "tokens go in at the
bottom, pass up through a stack of layers, and a distribution comes out the
top" — which is what a language model is, and which a stack of rings on a
shaft (the previous version) never said.

Bottom to top:

  * The **embedding**: a wide lattice plate, full of grid because it is full of
    numbers. Its depth against a block's is the square root of their parameter
    ratio, so it is about twice as deep because it genuinely holds about four
    times the numbers. The same plate is drawn again at the top, because the
    head is that tensor transposed and there is only one of it.
  * A row of **tokens** — small cubes — with a **residual stream** rising from
    each, straight through every layer to the head. Eight of them: a sketch of
    the window, not its length (``MAX_SEQ_LEN`` is 512, and 512 cubes are a
    smudge). This is the one count in the object that is not the model's.
  * Each **block**, in two sublayers. The lower is **attention**: a box with
    the causal fan on its front face — the last position looking back at every
    earlier one, arcs to further tokens drawn taller only so they do not lie on
    each other — and a comb of ticks on each end, one per head, countable when
    the side swings toward the room. The upper is the
    **MLP**: a bow-tie prism, its middle wider than its ends by the square root
    of the SwiGLU expansion, so a block looks as top-heavy as it actually is.
  * The **next-token distribution**: a row of bars above the head, the
    vocabulary ranked by probability, tallest first. Their heights are a shape
    (a power law), not a measurement — it is what a softmax over fifty thousand
    words looks like, and the reason the whole machine exists.

Which blocks exist depends on ``MODEL_ARCH``. The **plain** model (the default
since 2026-09-12, when depth recurrence was retired) is ``PLAIN_LAYERS``
identical blocks and nothing else: no loop, no gate. The **refiner** (retired,
still the 4B champion's) is its encoder blocks and then one block run again and
again: that one is drawn with a loop threaded around it per refinement pass,
and a small gate box above it.

Explode pulls the sublayers apart vertically and nothing else, because every
part is centred on the axis. The widget shows it with a sweep, not a turn: it
has a front, and the front is where the sequence reads left to right. Colour
is the rest of the animation: a "stack" wave runs up it, the data going through.
"""

import argparse
import ast
import math
import sys
from pathlib import Path

# Run as a script rather than imported as a package member, so the module next
# door is not on the path unless it is put there.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shapes import Obj, arc, bar, box, grid, prism, ring

# Proportions, in arbitrary units — the backend centres and scales whatever it
# is given, so only the ratios matter. Sized for a widget that is taller than
# it is wide, which is how a stack is shown.
TOKENS = 8
PITCH = 0.3  # Between token centres; sets the width of everything above them.
TOKEN = 0.11  # The cube.
WIDTH = TOKENS * PITCH + 0.2  # The plates and layers overhang the row a little.
DEPTH = 0.7  # A block, front to back.
STACK_LOW, STACK_HIGH = -1.35, 1.45  # Where the blocks live.
TOKEN_Y, EMBED_Y = -1.72, -2.0
HEAD_Y, LOGIT_Y = 1.72, 1.78
LOGIT_BARS, LOGIT_TALLEST = 20, 0.42
ARC_SEGMENTS = 10
GRID_COLS, GRID_ROWS = 10, 4

# What the shape is built from, and what to fall back on when a config computes
# a value rather than stating it. Every one of these changes the object.
WANTED = {
    "MODEL_ARCH": "plain",
    "LATENT_DIM": 960,
    "VOCAB_SIZE": 50304,
    "NUM_HEADS": 15,
    "PLAIN_LAYERS": 9,
    "REFINER_ENCODER_LAYERS": 7,
    "INFERENCE_DEPTH": 6,
}


def read_config(path: Path) -> dict:
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
                if isinstance(value, (int, str)):
                    found[target.id] = value
    return found


def mlp_hidden(dim: int) -> int:
    """The SwiGLU inner width, rounded the way the model rounds it."""
    return ((int(8 * dim / 3) + 63) // 64) * 64


def slab_ratio(dim: int, vocab: int) -> float:
    """How much deeper the embedding plate is drawn than one block.

    The square root of the parameter ratio, because these are areas on a screen
    and a count should read as an area — at a straight ratio the plate is four
    times a block and swamps the instrument it belongs to.
    """
    block = 4 * dim * dim + 3 * dim * mlp_hidden(dim)
    return math.sqrt((vocab * dim) / block)


def token_x(i: int) -> float:
    """Where the i-th position sits along the sequence."""
    return (i - (TOKENS - 1) / 2) * PITCH


def draw_attention(obj: Obj, low: float, high: float, heads: int) -> None:
    """The attention sublayer: a box, the causal fan on its front, heads on its ends.

    The fan is on the front face only: the widget sweeps this object rather
    than turning it, so the back is never shown, and a second fan there only
    doubled the lines through the front. The heads are ticks rather than
    panes: fifteen panes stacked front to back overlap into one grey sheet
    from the front and hide the fan behind it, while ticks on the end faces
    cost nothing until the side swings round.
    """
    box(obj, 0.0, (low + high) / 2, 0.0, WIDTH, high - low, DEPTH)
    last = token_x(TOKENS - 1)
    for j in range(TOKENS - 1):
        reach = (TOKENS - 1 - j) / (TOKENS - 1)
        arc(obj, token_x(j), last, low, (high - low) * math.sqrt(reach), DEPTH / 2, ARC_SEGMENTS)
    for x in (-WIDTH / 2, WIDTH / 2):
        for k in range(heads):
            z = -DEPTH / 2 + DEPTH * (k + 0.5) / heads
            obj.path([(x, low, z), (x, high, z)])


def draw_mlp(obj: Obj, low: float, high: float, expand: float) -> None:
    """The MLP sublayer: up to the hidden width and back down, as a bow-tie."""
    prism(
        obj, [(low, WIDTH, DEPTH), ((low + high) / 2, WIDTH, DEPTH * expand), (high, WIDTH, DEPTH)]
    )


def draw_block(obj: Obj, name: str, low: float, high: float, heads: int, expand: float) -> None:
    """One transformer block, as two parts so a wave lights them in turn."""
    slot = high - low
    obj.part(f"attn_{name}")
    draw_attention(obj, low, low + slot * 0.45, heads)
    obj.part(f"mlp_{name}")
    draw_mlp(obj, low + slot * 0.58, low + slot * 0.95, expand)


def build(conf: dict) -> Obj:
    """The whole instrument, bottom to top, for whichever architecture ships."""
    obj = Obj("TinyRefinementModel — generated by tools/mesh/trm.py")
    dim, heads = conf["LATENT_DIM"], conf["NUM_HEADS"]
    expand = math.sqrt(mlp_hidden(dim) / dim)
    plate = DEPTH * slab_ratio(dim, conf["VOCAB_SIZE"])

    obj.part("embed")
    grid(obj, EMBED_Y, WIDTH, plate, GRID_COLS, GRID_ROWS)

    obj.part("tokens")
    for i in range(TOKENS):
        box(obj, token_x(i), TOKEN_Y, 0.0, TOKEN, TOKEN, TOKEN)

    if conf["MODEL_ARCH"] == "plain":
        layers = conf["PLAIN_LAYERS"]
        slot = (STACK_HIGH - STACK_LOW) / layers
        for i in range(layers):
            draw_block(
                obj, str(i + 1), STACK_LOW + i * slot, STACK_LOW + (i + 1) * slot, heads, expand
            )
    else:
        _build_refiner(obj, conf, heads, expand)

    obj.part("head")
    grid(obj, HEAD_Y, WIDTH, plate, GRID_COLS, GRID_ROWS)

    # The vocabulary ranked by probability. A power law, because that is the
    # shape a softmax over a vocabulary has: a few words carry nearly all of it.
    obj.part("logits")
    step = WIDTH / LOGIT_BARS
    for k in range(LOGIT_BARS):
        x = -WIDTH / 2 + step * (k + 0.5)
        bar(obj, x, LOGIT_Y, LOGIT_Y + LOGIT_TALLEST / math.sqrt(k + 1), step * 0.5, 0.0)

    # One residual stream per position: the straight lines in the object,
    # because everything else here is something done to them.
    obj.part("stream")
    for i in range(TOKENS):
        obj.path([(token_x(i), TOKEN_Y + TOKEN / 2, 0.0), (token_x(i), HEAD_Y, 0.0)])
    return obj


def _build_refiner(obj: Obj, conf: dict, heads: int, expand: float) -> None:
    """The retired CausalRefiner: an encoder stack, then one block run again and again."""
    layers, depth = conf["REFINER_ENCODER_LAYERS"], conf["INFERENCE_DEPTH"]
    # The looped block takes a double slot: it is the one piece that runs more
    # than once, and the loops around it need the room.
    slot = (STACK_HIGH - STACK_LOW) / (layers + 2.5)
    for i in range(layers):
        draw_block(
            obj, f"encoder_{i + 1}", STACK_LOW + i * slot, STACK_LOW + (i + 1) * slot, heads, expand
        )

    low = STACK_LOW + layers * slot
    draw_block(obj, "refine", low, low + 1.6 * slot, heads, expand)
    # One loop per refinement pass, threaded around the block front to back,
    # spread along the sequence so they are countable.
    obj.part("passes")
    for k in range(depth):
        x = (k - (depth - 1) / 2) * WIDTH / (depth + 1)
        ring(obj, x, low + 0.8 * slot, DEPTH * 0.65 * expand, 0.9 * slot, 24)

    obj.part("gate")
    box(obj, 0.0, low + 2.1 * slot, 0.0, WIDTH * 0.3, 0.35 * slot, DEPTH * 0.5)


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

    shape = (
        f"{conf['PLAIN_LAYERS']} identical blocks, no loop"
        if conf["MODEL_ARCH"] == "plain"
        else f"{conf['REFINER_ENCODER_LAYERS']} encoder blocks + 1 looped · depth {conf['INFERENCE_DEPTH']}"
    )
    print(
        f"{conf['MODEL_ARCH']} · dim {conf['LATENT_DIM']} · vocab {conf['VOCAB_SIZE']} · "
        f"{conf['NUM_HEADS']} heads · {shape}"
    )
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
