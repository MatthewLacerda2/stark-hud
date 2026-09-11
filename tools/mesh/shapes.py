"""Writing an OBJ by hand: the file, and the handful of shapes a diagram needs.

Pure arithmetic and no Blender. Everything an architecture diagram is made of
turns out to be a ring, a lattice or a bar, and each of those is a loop over
``cos`` and ``sin`` — so the whole pipeline stays standard library and runs on
the machine that shows the board.

Nothing here starts a part. A part is a thing the widget colours and moves, and
deciding what belongs in one is composition, not geometry — so the caller says
``obj.part("encoder_3")`` and then draws as many shapes into it as that part is
made of.
"""

import math

Point = tuple[float, float, float]


class Obj:
    """An OBJ file being written: named parts, points, faces and closed curves."""

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

    def quads(self, base: int, rows: int, cols: int, wrap: bool) -> None:
        """Join a lattice of points into faces, closing it around if ``wrap``.

        Wrapping is what turns a strip into a ring rather than a fence, and it
        is the difference between a band with a seam in it and one without.
        """
        for r in range(rows - 1):
            for c in range(cols if wrap else cols - 1):
                nxt = (c + 1) % cols
                self.lines.append(
                    "f "
                    + " ".join(
                        str(i)
                        for i in (
                            base + r * cols + c,
                            base + r * cols + nxt,
                            base + (r + 1) * cols + nxt,
                            base + (r + 1) * cols + c,
                        )
                    )
                )

    def loop(self, points: list[Point]) -> None:
        """A closed curve, as an OBJ polyline.

        A curve rather than a surface when the thing genuinely is a path: giving
        a trajectory a tube makes it look like another part of the machine
        instead of the thing travelling through it.
        """
        base = self.add(points)
        order = [base + i for i in range(len(points))] + [base]
        self.lines.append("l " + " ".join(str(i) for i in order))

    def text(self) -> str:
        """The finished file."""
        return "\n".join([*self.lines, ""])


def _circle(radius: float, y: float, segments: int, phase: float = 0.0) -> list[Point]:
    """Points evenly around a horizontal circle."""
    return [
        (
            radius * math.cos(phase + 2 * math.pi * i / segments),
            y,
            radius * math.sin(phase + 2 * math.pi * i / segments),
        )
        for i in range(segments)
    ]


def band(obj: Obj, y: float, inner: float, outer: float, segments: int) -> None:
    """A flat ring lying in the horizontal plane."""
    base = obj.add(_circle(inner, y, segments) + _circle(outer, y, segments))
    obj.quads(base, 2, segments, wrap=True)


def web(obj: Obj, y: float, radius: float, rings: int, spokes: int) -> None:
    """A flat polar lattice — a disc drawn as a mesh rather than an outline.

    For the things in a model that are one enormous tensor. An outline would
    say "a disc this wide"; the lattice says "and it is full of numbers", which
    for a 48-million-parameter embedding is most of the point.
    """
    points: list[Point] = []
    for r in range(rings + 1):
        points += _circle(radius * (r + 1) / (rings + 1), y, spokes)
    obj.quads(obj.add(points), rings + 1, spokes, wrap=True)


def torus(obj: Obj, y: float, radius: float, tube: float, major: int, minor: int) -> None:
    """A solid ring: for the part that should read as machined rather than drawn."""
    points: list[Point] = []
    for i in range(major):
        angle = 2 * math.pi * i / major
        cx, cz = math.cos(angle), math.sin(angle)
        for j in range(minor):
            small = 2 * math.pi * j / minor
            out = radius + tube * math.cos(small)
            points.append((out * cx, y + tube * math.sin(small), out * cz))
    base = obj.add(points)
    obj.quads(base, major, minor, wrap=True)
    # quads() wraps the minor direction and walks the major one, so the last
    # cross-section is still open; this is the seam that closes the ring.
    for j in range(minor):
        nxt = (j + 1) % minor
        obj.lines.append(
            "f "
            + " ".join(
                str(i)
                for i in (
                    base + (major - 1) * minor + j,
                    base + (major - 1) * minor + nxt,
                    base + nxt,
                    base + j,
                )
            )
        )


def ticks(obj: Obj, y: float, inner: float, outer: float, count: float, width: float) -> None:
    """Radial bars around a ring — for anything a block has a countable number of.

    Drawn as bars sticking out of the rim rather than as extra segments in it,
    because a segment count is invisible on a circle: fifteen divisions in a
    smooth ring reads as a smooth ring. Fifteen teeth read as fifteen.
    """
    n = int(count)
    for i in range(n):
        angle = 2 * math.pi * i / n
        pts: list[Point] = []
        for radius in (inner, outer):
            for side in (-width, width):
                pts.append(
                    (
                        radius * math.cos(angle + side),
                        y,
                        radius * math.sin(angle + side),
                    )
                )
        base = obj.add(pts)
        obj.lines.append(f"f {base} {base + 1} {base + 3} {base + 2}")


def tube(obj: Obj, low: float, high: float, radius: float, sides: int) -> None:
    """A vertical shaft. A line would be a hairline; this has a thickness."""
    base = obj.add(_circle(radius, low, sides) + _circle(radius, high, sides))
    obj.quads(base, 2, sides, wrap=True)
