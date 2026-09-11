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
