"""Writing an OBJ by hand: the file, and the handful of shapes a diagram needs.

Pure arithmetic and no Blender. Everything an architecture diagram is made of
turns out to be a box, a lattice, a bar or a curve, and each of those is a
short loop over coordinates — so the whole pipeline stays standard library and
runs on the machine that shows the board.

Axes, so every caller agrees: ``x`` runs left to right, ``y`` runs up, ``z``
runs toward the camera (the widget draws the larger ``z`` brighter).

Nothing here starts a part. A part is a thing the widget colours and moves, and
deciding what belongs in one is composition, not geometry — so the caller says
``obj.part("attn_3")`` and then draws as many shapes into it as that part is
made of.
"""

import math

Point = tuple[float, float, float]


class Obj:
    """An OBJ file being written: named parts, points, faces and curves."""

    def __init__(self, note: str) -> None:
        self.lines: list[str] = [f"# {note}"]
        self.count = 0

    def part(self, name: str) -> None:
        """Start a new named object. This is the unit the widget draws and colours."""
        self.lines.append(f"o {name}")

    def add(self, points: list[Point]) -> int:
        """Write points, and hand back the 1-based index of the first."""
        base = self.count + 1
        for x, y, z in points:
            self.lines.append(f"v {x:.5f} {y:.5f} {z:.5f}")
        self.count += len(points)
        return base

    def face(self, indices: list[int]) -> None:
        """One polygon over points already written."""
        self.lines.append("f " + " ".join(str(i) for i in indices))

    def quads(self, base: int, rows: int, cols: int) -> None:
        """Join a lattice of points, written row by row, into faces."""
        for r in range(rows - 1):
            for c in range(cols - 1):
                at = base + r * cols + c
                self.face([at, at + 1, at + cols + 1, at + cols])

    def path(self, points: list[Point]) -> None:
        """An open curve, as an OBJ polyline.

        A curve rather than a surface when the thing genuinely is a path: giving
        a trajectory a tube makes it look like another part of the machine
        instead of the thing travelling through it.
        """
        base = self.add(points)
        self.lines.append("l " + " ".join(str(base + i) for i in range(len(points))))

    def text(self) -> str:
        """The finished file."""
        return "\n".join([*self.lines, ""])


def quad(obj: Obj, a: Point, b: Point, c: Point, d: Point) -> None:
    """One four-cornered face, given its corners in order around it."""
    obj.face([obj.add([a, b, c, d]) + i for i in range(4)])


def rect(obj: Obj, y: float, width: float, depth: float, z: float = 0.0) -> None:
    """A horizontal rectangle centred on the axis, ``width`` along x, ``depth`` along z."""
    hw, hd = width / 2, depth / 2
    quad(obj, (-hw, y, z - hd), (hw, y, z - hd), (hw, y, z + hd), (-hw, y, z + hd))


def box(obj: Obj, cx: float, cy: float, cz: float, w: float, h: float, d: float) -> None:
    """A rectangular box as its twelve edges: four faces are enough to draw them all."""
    x0, x1, y0, y1, z0, z1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2, cz - d / 2, cz + d / 2
    quad(obj, (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))
    quad(obj, (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1))
    quad(obj, (x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1))
    quad(obj, (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))


def prism(obj: Obj, levels: list[tuple[float, float, float]]) -> None:
    """A stack of horizontal rectangles joined at the corners.

    Each level is ``(y, width, depth)``. Three levels with a wide middle is the
    bow-tie an MLP has always been drawn as — up to the hidden width and back.
    """
    for y, w, d in levels:
        rect(obj, y, w, d)
    for sx in (-1, 1):
        for sz in (-1, 1):
            obj.path([(sx * w / 2, y, sz * d / 2) for y, w, d in levels])


def grid(obj: Obj, y: float, width: float, depth: float, cols: int, rows: int) -> None:
    """A flat rectangular lattice — a plate drawn as a mesh rather than an outline.

    For the things in a model that are one enormous tensor. An outline would
    say "a plate this wide"; the lattice says "and it is full of numbers", which
    for a 48-million-parameter embedding is most of the point.
    """
    points: list[Point] = []
    for r in range(rows + 1):
        z = -depth / 2 + depth * r / rows
        for c in range(cols + 1):
            points.append((-width / 2 + width * c / cols, y, z))
    obj.quads(obj.add(points), rows + 1, cols + 1)


def arc(obj: Obj, x0: float, x1: float, y: float, height: float, z: float, segments: int) -> None:
    """A half-ellipse standing on the line from ``x0`` to ``x1``, facing the camera."""
    mid, half = (x0 + x1) / 2, (x1 - x0) / 2
    obj.path(
        [
            (
                mid - half * math.cos(math.pi * i / segments),
                y + height * math.sin(math.pi * i / segments),
                z,
            )
            for i in range(segments + 1)
        ]
    )


def bar(obj: Obj, x: float, low: float, high: float, width: float, z: float) -> None:
    """A thin upright bar facing the camera: one column of a histogram."""
    quad(
        obj,
        (x - width / 2, low, z),
        (x + width / 2, low, z),
        (x + width / 2, high, z),
        (x - width / 2, high, z),
    )


def ring(obj: Obj, cx: float, cy: float, rx: float, ry: float, segments: int) -> None:
    """An ellipse in the vertical plane through the axis (the y-z plane), for a loop."""
    points = [
        (
            cx,
            cy + ry * math.sin(2 * math.pi * i / segments),
            rx * math.cos(2 * math.pi * i / segments),
        )
        for i in range(segments)
    ]
    obj.path([*points, points[0]])
