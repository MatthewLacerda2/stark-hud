"""Reading an OBJ file down to the only thing the board draws: edges.

An OBJ is a text format with a dozen record types and this reads four of them —
``o``, ``v``, ``f`` and ``l``. Everything else is skipped without comment:
normals, texture coordinates, materials, smoothing groups and the rest describe
how a surface should be lit, and nothing here is lit.

Parsed on this machine rather than in the browser, for three reasons. The file
never leaves the host, which is the same rule every other local-file widget
follows. The television gets edges instead of a text file several times their
size. And "only the mesh matters" becomes a function with tests around it rather
than a sentence in a comment.
"""

from pathlib import Path

from repositories import board as repo
from schemas.board import ItemRead
from schemas.mesh import MeshPart, Wireframe
from schemas.notifications import NotificationCreate
from services import notifications

# The most lines this will hand a browser. A wireframe is drawn one stroke per
# edge on a canvas, on a television that is the slowest machine in the house, so
# the ceiling is about what it can draw sixty times a second rather than about
# what the file contains. It is also roughly where a wireframe stops being a
# picture of an object and becomes a grey smudge, so decimating to fit is not a
# workaround — it is what makes the model readable in the first place.
MAX_EDGES = 40_000

# What the model is scaled into: the longest side of its bounding box becomes
# this, centred on the origin. So a part that is a tenth of the model is a tenth
# of a unit here, whether the file was saved in millimetres or in miles.
UNIT = 1.0

# Faces are dropped, not triangulated, past this many corners. An n-gon's edges
# are its outline, which is all this needs, so the count is only a guard against
# a malformed line claiming a face with a hundred thousand corners in it.
MAX_FACE_CORNERS = 512

Point = tuple[float, float, float]


class BadMeshError(Exception):
    """Raised when a file cannot be read as a mesh, saying what would work."""


class MeshTooBigError(Exception):
    """Raised when a model has more edges than the board will draw.

    Names the converter, because the fix is one command rather than a smaller
    model: ``tools/mesh/convert.py`` decimates to a target on the way through.
    """

    def __init__(self, edges: int) -> None:
        self.edges = edges
        super().__init__(
            f"That model is {edges:,} edges and the board draws at most "
            f"{MAX_EDGES:,}. Run it through tools/mesh/convert.py, which "
            f"decimates to fit, and point the widget at what that writes."
        )


def _vertex(fields: list[str]) -> Point:
    """One ``v`` line as a point, ignoring any colour trailing the coordinates."""
    try:
        return (float(fields[0]), float(fields[1]), float(fields[2]))
    except (IndexError, ValueError) as exc:
        raise BadMeshError(f"Not a vertex: 'v {' '.join(fields)}'") from exc


def _index(field: str, seen: int) -> int:
    """One corner of a face, as a zero-based index into the vertices so far.

    Two things make this more than ``int(field) - 1``. A corner is written
    ``vertex/texture/normal`` and only the first part is a position. And the
    index may be negative, which counts back from the most recent vertex rather
    than forward from the first — so it can only be resolved while reading,
    against how many have been seen at that point in the file.
    """
    try:
        found = int(field.split("/", 1)[0])
    except ValueError as exc:
        raise BadMeshError(f"Not a vertex index: {field!r}") from exc
    resolved = found - 1 if found > 0 else seen + found
    if not 0 <= resolved < seen:
        raise BadMeshError(f"Face refers to vertex {found}, which is not in the file")
    return resolved


def _edges_of(corners: list[int]) -> list[tuple[int, int]]:
    """The outline of a face, or the segments of a polyline, as vertex pairs.

    A face closes and a line does not, but the difference does not matter here:
    an OBJ ``l`` with the same start and end is closed by the same wrap, and one
    duplicate pair is removed by the deduplication the caller does anyway.
    """
    return [(corners[i], corners[(i + 1) % len(corners)]) for i in range(len(corners))]


class _Part:
    """One object out of the file, collected while reading.

    Holds edges as global vertex indices and remaps them at the end. The remap
    cannot happen while reading: OBJ numbers its vertices once across the whole
    file, so an object's faces point into a shared list, and which of those
    points this object actually uses is only known once its last face is read.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.edges: set[tuple[int, int]] = set()

    def add(self, corners: list[int]) -> None:
        """Record a face or a polyline as undirected edges.

        Sorted into a set, so the edge two neighbouring faces share is stored
        once. On anything closed that is half the lines on the screen, and two
        strokes down the same pixels is not a drawing that is twice as good.
        """
        for a, b in _edges_of(corners):
            if a != b:
                self.edges.add((a, b) if a < b else (b, a))

    def resolve(self, points: list[Point], shift: Point, scale: float) -> MeshPart:
        """Turn shared indices into this part's own points, normalised.

        ``used`` is built in sorted order rather than in the order the faces
        mention the points, which costs nothing and means the same file always
        produces byte-identical output — worth having when the thing you are
        debugging is a picture.
        """
        used = sorted({i for edge in self.edges for i in edge})
        local = {old: new for new, old in enumerate(used)}
        verts: list[float] = []
        for old in used:
            point = points[old]
            verts += [(point[axis] - shift[axis]) * scale for axis in range(3)]
        edges: list[int] = []
        for a, b in sorted(self.edges):
            edges += [local[a], local[b]]
        middle = [sum(verts[axis::3]) / len(used) if used else 0.0 for axis in range(3)]
        return MeshPart(name=self.name, verts=verts, edges=edges, center=middle)


def _read(text: str) -> tuple[list[Point], list[_Part]]:
    """Walk the file once, collecting points and the objects that use them.

    A file with no ``o`` line at all is one unnamed part, which is what most
    exporters that were handed a single mesh produce. Faces appearing before any
    ``o`` land there too, rather than being dropped for arriving early.
    """
    points: list[Point] = []
    parts: list[_Part] = [_Part("mesh")]
    for raw in text.splitlines():
        # Stripped before splitting: an indented `v` is still a vertex, and some
        # exporters indent the faces under their object line.
        head, _, rest = raw.strip().partition(" ")
        fields = rest.split()
        if head == "v":
            points.append(_vertex(fields))
        elif head == "o":
            parts.append(_Part(rest.strip() or f"part {len(parts)}"))
        elif head in ("f", "l") and fields:
            if len(fields) > MAX_FACE_CORNERS:
                raise BadMeshError(f"A face with {len(fields)} corners is not a face")
            parts[-1].add([_index(field, len(points)) for field in fields])
    return points, [part for part in parts if part.edges]


def _bounds(points: list[Point]) -> tuple[Point, Point]:
    """The corners of the box every point fits inside."""
    return (
        (min(p[0] for p in points), min(p[1] for p in points), min(p[2] for p in points)),
        (max(p[0] for p in points), max(p[1] for p in points), max(p[2] for p in points)),
    )


def parse(text: str) -> Wireframe:
    """An OBJ file as a wireframe: parts, edges, centred and scaled to fit.

    Normalising here is what lets the widget take any file at all. A model may
    be in millimetres, in metres, or sitting a hundred units from the origin
    because that is where it was when somebody exported it, and none of that is
    something to make a person discover from an empty-looking widget. Centre it,
    scale the longest side to one, and every model arrives the same size.
    """
    points, parts = _read(text)
    if not points or not parts:
        raise BadMeshError(
            "No mesh in that file: nothing in it declares vertices and faces. "
            "An OBJ of curves or points alone has no edges to draw."
        )
    total = sum(len(part.edges) for part in parts)
    if total > MAX_EDGES:
        raise MeshTooBigError(total)

    low, high = _bounds(points)
    span = [high[axis] - low[axis] for axis in range(3)]
    middle = (
        (low[0] + high[0]) / 2,
        (low[1] + high[1]) / 2,
        (low[2] + high[2]) / 2,
    )
    # A flat model — a plane, a logo, anything with no depth — has a zero side,
    # and the longest side is what scales it, so only an empty model divides by
    # nothing. That one is already refused above; this guard is for the model
    # whose every point is the same point.
    widest = max(span)
    scale = UNIT / widest if widest > 0 else 1.0
    return Wireframe(
        parts=[part.resolve(points, middle, scale) for part in parts],
        source_size=span,
    )


def read(path: str) -> Wireframe | None:
    """The wireframe at a path, or ``None`` when there is no file there.

    ``None`` rather than an exception for a missing file, because a missing file
    is not an error here — it is the thing the caller is watching for, and the
    widget that pointed at it is about to be taken off the board.
    """
    target = Path(path)
    if not target.is_file():
        return None
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise BadMeshError(f"Could not read {path}: {exc}") from exc
    return parse(text)


def forget(item: ItemRead, path: str) -> str:
    """Take a mesh widget off the board because its file is no longer there.

    The mesh widget is the one file-backed widget that does this. A picture or a
    video whose file has moved draws a placeholder naming the path and waits, on
    the grounds that the file may come back; this one removes itself, which the
    owner of the board asked for so that a board left running does not silently
    fill up with widgets pointing at models that were tidied away months ago.

    It is worth a later session knowing what that costs, because the cost is not
    theoretical here. A 404 means "not visible from inside the container right
    now", which is not the same as "deleted": `/mnt/d_drive` is a bind mount and
    can be late, a re-export unlinks the file before it writes the new one, and
    only `${HOME}` and that drive are mounted at all. In each of those the file
    is fine and the widget goes anyway, taking its place, size and description
    with it.

    Which is why this announces itself. Removal is written to the inbox naming
    the file, so a widget that disappears while nobody was watching leaves a line
    behind saying which model it was — the board is reviewed by looking at the
    television, and a widget that simply stops being there tells nobody anything.

    Removing the item is all that is needed to take it out of `board.hud` too:
    the repository marks the store dirty and the flusher writes the file.
    """
    repo.remove(item.id)
    notifications.create(
        NotificationCreate(
            title="Mesh widget removed",
            body=f"{path} is no longer there.",
            level="warn",
            source="mesh",
        )
    )
    return f"{path} is gone, so the widget showing it has been removed from the board."
