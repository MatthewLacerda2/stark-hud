"""What a flow shows: boxes, and the arrows that say one leads to another.

Its own module for the reason the chart, the gantt and the mesh have one — a
payload made of two further models is not one more block of fields, and
``schemas.payloads`` is at the house limit of 350 lines. ``hud_mcp/flows.py`` is
the tool that matches it.

The geometry here is copied inward from ``scorsese_core::shape``, which solved
the same problem for a video renderer: a diagram that has to survive being
re-rendered at a different size. Every number is a **fraction of the widget** —
``x`` and ``w`` of its width, ``y`` and ``h`` of its height — so the drawing
means the same thing in a 3x2 widget and in a 16x9 one. Nothing here is a pixel
and nothing here is stored computed: where a node without a position ends up is
a reading the browser takes, the way ``GanttPayload`` refuses to store its own
window.

**The word `node` is correct here and only here.** ``CLAUDE.md`` bans it for
widgets because a node suggests a graph; inside a flow there is a graph. The
``text-node-*`` type scale in the stylesheet is the older, unrelated sense of
the word and means *widget*.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.colour import Colour
from schemas.icon import Icon

# The two shapes a box comes in, and the list is meant to stay this short.
# scorsese holds the same line and gives the reason: a rectangle, an ellipse and
# an arrow are what a diagram is made of — boxes are its nouns and arrows its
# verbs, and polygons, stars and arbitrary paths are a drawing program growing
# inside something that was not one. A decision is said by the words on the two
# arrows leaving a node, not by a diamond nobody can read from a sofa.
#
# `ellipse` rather than `circle` because the two dimensions are fractions of
# different things — width of the widget's width, height of its height — so
# picking one axis to measure both against would be a different bug in every
# widget size.
FlowShape = Literal["rectangle", "ellipse"]

# Where on a box an arrow meets it, as ``scorsese_core::shape::Side``.
#
# `center` is the honest answer when an arrow is meant to point *at* a box
# rather than to touch it; it is drawn over the box, which is what was asked
# for.
FlowSide = Literal["left", "right", "top", "bottom", "center"]

# How an arrow gets from one end to the other. `s` leaves each end along that
# end's own outward normal, which is the shape two boxes side by side want — a
# straight diagonal between them reads as a mistake. Which axis it bows along is
# deliberately not a field; scorsese: "it is not a question an author has an
# opinion about."
FlowCurve = Literal["straight", "s"]

# Which ends of an arrow carry a head. This is what makes a plain connecting
# line not a kind of its own — scorsese again: "it is an arrow that points at
# nothing." `end` is the default because an arrow is drawn to say *this leads to
# that*, and that reading has a direction.
FlowHeads = Literal["none", "end", "both"]

# The most a corner can be rounded: half the box's shorter side, where the two
# corners of that side meet and the end has become a semicircle. Past it there
# is no straight edge left to round.
MAX_RADIUS = 0.5


class FlowNode(BaseModel):
    """One box in a flow, with a word in it.

    A box either names its whole rectangle — all four of ``x``, ``y``, ``w``,
    ``h`` — or names none of it and is laid out for. Half a rectangle has no
    honest reading, and "the widget will fit the rest around what you gave it"
    is a layout engine with a special case in it.

    Nodes may overlap each other and nothing enforces distance between them. The
    board refuses overlap because the board auto-places and is finite; inside a
    flow the author placed both deliberately, and a small box drawn over a larger
    one is a legitimate drawing.
    """

    model_config = ConfigDict(extra="forbid")

    # What a link names this box by. Unique within the flow — a duplicate is
    # refused naming it, because a link to the second of two boxes called
    # "build" would silently draw to the first.
    id: str
    text: str
    shape: FlowShape = "rectangle"
    # How rounded the corners are, as a fraction of the box's **own shorter
    # side** rather than of the widget: 0 is a square corner and 0.5 is a pill,
    # whatever size the box is and whatever shape the widget is. Copied outright
    # from ``Geometry::Rectangle``, whose comment gives the reason — a widget
    # fraction could be larger than the box it rounds, which is nonsense nothing
    # can catch until something works out the pixels. It also keeps corners
    # circular instead of elliptical, since one number then means one distance
    # rather than two. Ignored by an ellipse, which is all corner.
    radius: float = Field(default=0.18, ge=0.0, le=MAX_RADIUS)
    # The box's colour: its interior is a wash of this and its outline is this
    # at full strength — *wash areas, never marks*. Left out it takes the
    # widget's own ink, which over the board's video is a pane of smoked glass.
    # An eight-digit hex carries its own alpha and is drawn as written.
    color: Colour | None = None
    # Where the box sits and how big it is, all in 0-1 from the widget's
    # top-left. All four or none. Out of 0-1 is refused rather than clipped,
    # this widget's far edge included: it does not scroll and there is no
    # off-screen for anything to come in from.
    x: float | None = None
    y: float | None = None
    w: float | None = None
    h: float | None = None

    @model_validator(mode="after")
    def _a_whole_rectangle_or_none_of_one(self) -> "FlowNode":
        """Refuse half a box, and one that would be drawn off the widget."""
        given = [n for n, v in self._rect().items() if v is not None]
        if given and len(given) < 4:
            raise ValueError(
                f"node {self.id!r} gives only {', '.join(given)}; a box is placed by all "
                f"four of x, y, w and h, or by none of them"
            )
        if not given:
            return self
        for edge, near, far in (("x", self.x, self.w), ("y", self.y, self.h)):
            assert near is not None and far is not None
            if far <= 0:
                raise ValueError(f"node {self.id!r} has no width or height to draw")
            if near < 0 or near + far > 1:
                raise ValueError(
                    f"node {self.id!r} runs from {edge}={near:g} to {near + far:g}, which "
                    f"is outside the widget; a flow is clipped, not scrolled, so every "
                    f"edge has to land inside 0-1"
                )
        return self

    def _rect(self) -> dict[str, float | None]:
        """The four numbers that place this box, by name."""
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @property
    def placed(self) -> bool:
        """Whether this box says where it sits."""
        return self.x is not None


class FlowLink(BaseModel):
    """An arrow from one box to another.

    ``source`` and ``target`` rather than ``from`` and ``to``: ``from`` is a
    Python keyword, and the usual answer — ``from_`` with an alias — is a trap
    in this codebase specifically. The board is serialised down three different
    paths, and only one of them passes ``by_alias``, so the same link would
    reach the browser as ``from`` over HTTP and ``from_`` over the socket. One
    spelling everywhere is worth more than the nicer word.
    """

    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    # Which side of each box the arrow meets, or None to let the widget pick the
    # pair of facing sides. This is a deliberate divergence from scorsese, which
    # *requires* the author to choose because there an attached clip moves over
    # time and an arrow picking its own side would rearrange itself between two
    # renders. Nothing in a flow moves: the layout is a pure function of the
    # payload, so the same payload draws the same arrow forever.
    source_side: FlowSide | None = None
    target_side: FlowSide | None = None
    # A word on the arrow — what makes two arrows out of one box a decision
    # rather than a fork. Dropped when the arrow is too short to hold it: a word
    # half-overlapping a line is worse than no word.
    label: str | None = None
    curve: FlowCurve = "straight"
    heads: FlowHeads = "end"
    # Full-strength ink, whatever it is: an arrow is a mark and marks are never
    # washed. A hairline at a third strength over a moving video is not faint
    # from six feet away, it is absent.
    color: Colour | None = None


class FlowPayload(BaseModel):
    """A diagram of boxes and arrows, drawn whole inside one widget.

    The thing no other widget here can say: *this leads to that*. A deployment,
    a morning routine, the shape of a pipeline, a decision with two ways out.

    **The diagram is the widget and the arrow is a line inside it.** A
    free-standing arrow joining two widgets would make the board a canvas, every
    widget a node and dragging load-bearing — the exact opposite of what
    ``CLAUDE.md`` settles under *looks beat handling*. So a flow is drawn whole,
    the way a chart draws its own axes.

    Nothing in it is interactive: no click, no hover, no selection, no per-node
    handle. The television has no pointer and the sofa has no keyboard.

    A flow that changes is rewritten whole by ``key`` through the panel path.
    There is deliberately no ``add_to_flow`` and no per-node write until a writer
    exists that genuinely cannot rewrite the whole thing.
    """

    # Set here rather than inherited, like the chart, the gantt and the mesh:
    # this module cannot import the base in ``payloads`` without a cycle, since
    # that module imports this one.
    model_config = ConfigDict(extra="forbid")

    kind: Literal["flow"] = "flow"
    title: str | None = None
    icon: Icon | None = None
    nodes: list[FlowNode] = []
    links: list[FlowLink] = []

    @model_validator(mode="after")
    def _a_diagram_that_can_be_drawn(self) -> "FlowPayload":
        """Refuse the four ways a flow is wrong, each in a sentence naming it.

        Refused rather than patched up, for the reason the radial refuses a
        fourth ring: a widget that silently draws something other than what was
        dictated is invisible from the sofa and the caller is never told. The
        sentence is the whole product here — whoever wrote this cannot see the
        board and has only this line to work out what it typed wrongly.
        """
        self._one_box_per_name()
        self._all_placed_or_none_placed()
        self._every_arrow_joins_two_boxes()
        return self

    def _one_box_per_name(self) -> None:
        """A link names a box; two boxes with one name make that ambiguous."""
        seen: set[str] = set()
        for node in self.nodes:
            if node.id in seen:
                raise ValueError(
                    f"two nodes are called {node.id!r}; a link names a node by its id, so "
                    f"the ids have to be different"
                )
            seen.add(node.id)

    def _all_placed_or_none_placed(self) -> None:
        """Either every box says where it sits, or none does."""
        placed = [n.id for n in self.nodes if n.placed]
        loose = [n.id for n in self.nodes if not n.placed]
        if placed and loose:
            raise ValueError(
                f"{', '.join(repr(n) for n in placed)} say where they sit and "
                f"{', '.join(repr(n) for n in loose)} do not; place every node or none of "
                f"them, because a half-placed flow has no honest reading"
            )

    def _every_arrow_joins_two_boxes(self) -> None:
        """Both ends of every arrow name a box, and two different ones."""
        known = {n.id for n in self.nodes}
        drawn: set[tuple[str, str]] = set()
        for link in self.links:
            for end, name in (("source", link.source), ("target", link.target)):
                if name not in known:
                    raise ValueError(
                        f"a link's {end} is {name!r}, which is not a node in this flow; "
                        f"it has {', '.join(sorted(repr(n) for n in known)) or 'no nodes'}"
                    )
            if link.source == link.target:
                raise ValueError(
                    f"a link joins {link.source!r} to itself; a flow draws no loop back "
                    f"into the same node"
                )
            pair = (link.source, link.target)
            if pair in drawn:
                raise ValueError(
                    f"{link.source!r} leads to {link.target!r} twice; a flow draws one "
                    f"arrow per pair, so the second would be laid exactly over the first"
                )
            drawn.add(pair)
