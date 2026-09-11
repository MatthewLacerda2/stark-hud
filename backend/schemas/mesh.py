"""What a mesh widget shows, and the wireframe the browser is handed for it.

Its own module for the reason the chart and the gantt have one: the payload is
four fields, but the geometry beside it is a second model with a second shape,
and ``schemas.payloads`` is at the house limit.

The split down the middle of this file is the whole design. ``MeshPayload`` is
what lives on the board and in ``board.hud`` — a path and three numbers, small
enough that a person can still read the board file. ``Wireframe`` is what comes
back from ``/api/v1/mesh/{id}``, is never stored anywhere, and is rebuilt from
the file on disk whenever a browser asks. A reactor is 350 vertices and a
downloaded model is a hundred thousand; none of that belongs in a board file
that is rewritten every few seconds.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    """A 3D object drawn as a wireframe, turning on the spot.

    Only the mesh is read. Materials, textures, normals, UVs and whatever
    animation the file was carrying are all dropped on the way in — a hologram
    is edges and nothing else, so there is nothing here for them to be.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["mesh"] = "mesh"
    # Where the OBJ is on the machine running the board. Never sent to a
    # browser: the geometry is fetched by the widget's id, the way a picture is.
    path: str
    # Turns per second about the upright axis. Slow by default and deliberately
    # so — this is read from a sofa, and a model going round once every twelve
    # seconds reads as a thing on a turntable, while anything brisk reads as a
    # loading spinner.
    spin: float = Field(default=0.08, ge=-2.0, le=2.0)
    # How far the camera sits above the object, in degrees. Dead level is the
    # one angle at which a flat object is invisible for half its turn, so the
    # default is off-level: enough to see the top of the thing without the view
    # becoming a plan.
    tilt: float = Field(default=16.0, ge=-89.0, le=89.0)
    # How far the parts are pushed apart, where 0 is assembled and 1 moves each
    # part a full model-width out along the line from the middle of the object.
    # Only ever as good as the file: a model saved as one object has one part
    # and nothing to come apart from.
    explode: float = Field(default=0.0, ge=0.0, le=1.0)
    # What colour each part is drawn in, keyed by the part's name in the file.
    # A key may be a glob — ``encoder_*`` names seven rings without writing
    # seven lines — and where more than one pattern matches a part, the longest
    # pattern wins, so a name beats a wildcard without needing an order.
    #
    # A part named here keeps this colour and does not take the wave. That is
    # how the two compose: pin the parts that mean something, let the rest
    # breathe. A part named by neither takes the widget's own colour.
    colors: dict[str, Colour] | None = None
    # A colour travelling through the model, or None for a wireframe that just
    # sits there in one colour.
    wave: MeshWave | None = None


class MeshPart(BaseModel):
    """One named object out of the file, as points and the lines between them.

    Flat arrays rather than lists of triples or pairs. A triple written as
    ``[0.1, 0.2, 0.3]`` costs three brackets and two commas over the numbers
    themselves, and at a hundred thousand vertices that punctuation is most of
    the response. The browser reads them three and two at a time.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    # x, y, z, x, y, z, … — normalised so the whole model fits a unit cube
    # centred on the origin, whatever units the file was saved in.
    verts: list[float]
    # Pairs of indices into ``verts`` (counted in points, not in floats), each
    # pair one line to draw. Every edge appears once: a cube is twelve lines,
    # not the twenty-four its six faces would each claim.
    edges: list[int]
    # The middle of this part, in the same normalised space. The direction from
    # the origin to here is the direction the part travels when exploded, which
    # is why it is computed once on this side rather than every frame on the TV.
    center: list[float]


class Wireframe(BaseModel):
    """A whole model, ready to draw. Rebuilt from the file on every request."""

    model_config = ConfigDict(extra="forbid")

    parts: list[MeshPart]
    # What the model measured before it was normalised, in whatever units the
    # file used. Nothing draws this — it is here so that a model arriving at the
    # wrong scale is a number somebody can look at rather than a guess.
    source_size: list[float]
