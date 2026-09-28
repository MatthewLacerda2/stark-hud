"""What a mesh widget shows: which model file, and how it is looked at.

Its own module for the reason the chart and the gantt have one: the payload is
a dozen fields and ``schemas.payloads`` is at the house limit.

The model itself is never in here. ``MeshPayload`` is what lives on the board and
in ``board.hud`` — a path and the numbers that say how to look at it, small
enough that a person can still read the board file. The file is served as it is
from ``/api/v1/mesh/{id}`` and read by the browser; a model can be megabytes,
and none of that belongs in a board file that is rewritten every few seconds.
"""

from pathlib import PurePath
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from schemas.colour import Colour

# Which way a colour wave travels through a model.
#
#   "stack" runs it up the object, bottom to top. On anything built as a
#   pipeline that is the data going through: embedding, then the blocks, then
#   the head. It lights every part, because every part has a height.
#
#   "loop" runs it around the upright axis instead, so parts light in the order
#   they sit around the circle. Parts standing ON the axis have no angle to take
#   a turn from and are left at the widget's own colour — which is the point
#   rather than a gap: on a model whose loop is a ring of parts around a shaft,
#   this lights the ring and leaves the shaft alone.
WaveMode = Literal["stack", "loop"]

# The model files a browser can open, and what it is told each one is. glTF has
# registered types; OBJ and FBX have none anybody agrees on, and the loaders read
# the bytes whatever the header says, so they go as what they are.
MODEL_TYPES = {
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".obj": "text/plain",
    ".fbx": "application/octet-stream",
}


def _openable(path: str) -> str:
    """The path, if it names a kind of model the browser can open.

    Only the name is judged, not the file: a model that is not there yet is a
    widget that removes itself when it is first drawn, the same as one whose
    file goes later. A .blend is the one people will reach for, and only Blender
    reads it — Blender is on the host, not in the container — so the refusal
    says how to get from one to the other.
    """
    suffix = PurePath(path).suffix.lower()
    if suffix not in MODEL_TYPES:
        raise ValueError(
            f"The board cannot open a {suffix or 'suffixless'} file; it takes "
            f"{', '.join(MODEL_TYPES)}. For a .blend or anything else Blender "
            f"opens, `python tools/mesh/convert.py {path}` writes a .glb beside it."
        )
    return path


ModelPath = Annotated[str, AfterValidator(_openable)]


class MeshWave(BaseModel):
    """A colour running through a model, over and over.

    The one animation a wireframe can really carry. A board that only moves
    when a number changes reads as a screen; this is what makes a widget read
    as switched on, which on a television in a room somebody lives in is worth
    more than it sounds.

    It is not a highlight sweeping across an otherwise plain object. Every part
    sits at its own point on the ramp at every moment, so the model always
    holds the whole gradient and the wave is that gradient travelling. A lit
    band moving over dark geometry leaves most of the object dead at any
    instant; this leaves none of it dead.
    """

    model_config = ConfigDict(extra="forbid")

    mode: WaveMode = "stack"
    # How long one full pass takes. Slow, for the same reason the spin is: a
    # colour that hurries reads as a warning rather than as a thing being alive.
    seconds: float = Field(default=8.0, ge=0.5, le=600.0)
    # The colours it runs through, in order, and the list wraps — the last
    # leads back into the first. So ("white", "info", "destructive") is a cycle
    # that returns through red to white; to come back the way it went, say so:
    # ("white", "info", "destructive", "info").
    colors: list[Colour] = Field(min_length=2, max_length=8)
    # How much of the ramp the model spans at one moment. At 1 the far ends of
    # the object are a full cycle apart, so every colour in the list is on
    # screen at once; below that the model holds less of the ramp and the whole
    # thing pulses more as one. Above 1 the ramp repeats along the model, which
    # is how a wave gets more than one crest.
    spread: float = Field(default=1.0, gt=0.0, le=4.0)


class MeshPayload(BaseModel):
    """A 3D model drawn as a hologram: translucent light, rim-lit, with its edges.

    The file is drawn as it was made — its parts, their pivots and any animation
    saved in it — but not as it was lit: materials, textures and cameras in the
    file are ignored. The look is the board's, and so is the camera.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["mesh"] = "mesh"
    # Where the model file is on the machine running the board: .glb, .gltf,
    # .fbx or .obj. Never sent to a browser: the file is fetched by the widget's
    # id, the way a picture is.
    path: ModelPath
    # Turns per second about the upright axis. 0 holds the model still, which is
    # a fine way to show one; anything turning should turn slowly, because a
    # model going round once every twelve seconds reads as a thing on a
    # turntable while anything brisk reads as a loading spinner.
    spin: float = Field(default=0.0, ge=-2.0, le=2.0)
    # How far the model swings each way, in degrees, instead of going round. At
    # 0 it turns full circle. Anything else makes it sweep: it turns to this
    # angle, slows into it, and comes back the other way, over and over — for a
    # model with a front, which a full turn shows for a quarter of the time.
    # ``spin`` still sets the pace: one there-and-back takes 1/spin seconds.
    sweep: float = Field(default=0.0, ge=0.0, le=180.0)
    # Where the model stands before any spin or sweep, in degrees about the
    # upright, counter-clockwise seen from above. 0 is the model's own front
    # facing the viewer. A model held still is usually wanted a little off
    # dead-on, which is this.
    heading: float = Field(default=0.0, ge=-360.0, le=360.0)
    # How far the camera sits above the object, in degrees. Dead level is the
    # one angle at which a flat object is invisible for half its turn, so the
    # default is off-level: enough to see the top of the thing without the view
    # becoming a plan.
    tilt: float = Field(default=16.0, ge=-89.0, le=89.0)
    # The camera's field of view, in degrees. Narrow flattens the model toward a
    # drawing; wide makes the near side swell. The model is framed to fit at any
    # value, so this changes the perspective, not the size.
    fov: float = Field(default=30.0, ge=5.0, le=120.0)
    # How big the model is drawn, against the size that just fits the widget.
    # Above 1 crops into it; below leaves room around it.
    zoom: float = Field(default=1.0, ge=0.1, le=10.0)
    # Where the model sits in the widget, as a fraction of the widget's width and
    # height: 0.25 moves it a quarter of the way right (or up). For showing one
    # end of a large model rather than the middle of it.
    pan_x: float = Field(default=0.0, ge=-1.0, le=1.0)
    pan_y: float = Field(default=0.0, ge=-1.0, le=1.0)
    # How far the parts are pushed apart, where 0 is assembled and 1 moves each
    # part a full model-width out along the line from the middle of the object.
    # Only ever as good as the file: a model saved as one object has one part
    # and nothing to come apart from.
    explode: float = Field(default=0.0, ge=0.0, le=1.0)
    # What colour each part is drawn in, keyed by the part's name in the file —
    # an object in an OBJ, a node in a glTF. A rule on a node covers everything
    # under it. A key may be a glob — ``encoder_*`` names seven rings without
    # writing seven lines — and where more than one pattern matches a part, the
    # longest pattern wins, so a name beats a wildcard without needing an order.
    #
    # A part named here keeps this colour and does not take the wave. That is
    # how the two compose: pin the parts that mean something, let the rest
    # breathe. A part named by neither takes the widget's own colour.
    colors: dict[str, Colour] | None = None
    # A colour travelling through the model, or None for a model that just sits
    # there in its colours.
    wave: MeshWave | None = None
