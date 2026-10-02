"""Where each box of an architecture diagram sits, as fractions of its widget.

The flow widget can lay out boxes it is not told about, and does it in ranks
the way this does — but every box takes its rank's slot whatever shape that is,
and a rank keeps the order the payload listed it in. On rusty's 20 modules
that drew slivers too thin to hold an icon, joined by arrows crossing the whole
widget. So the collector places them itself:

- **Rows, top to bottom.** A part sits above what it uses — longest path, so a
  part is never beside one of its own dependencies — which puts whoever
  depends on the rest at the top and the foundation at the bottom, the way an
  architecture diagram is read. A cycle has no top, so the arrow that closes
  one is cut for the ranking and still drawn, pointing back up.
- **Every row has as many seats as the busiest**, so a short row can sit its
  boxes under their neighbours rather than spread out. Which box takes which
  seat starts from the barycentre heuristic and is then improved by looking at
  the drawing itself: swap two boxes, or move one to a free seat, whenever that
  makes the straight arrows between box centres cost less. An arrow through a
  box costs most, since it reads as a dependency that is not there; a crossing
  next; length only breaks ties. Deterministic: the same graph draws the same
  picture every hour.
- **Square boxes**, square at the widget's shape (hence `aspect`), as large as
  the busiest row and the number of rows allow — for the part that most others
  use. A box shrinks with how few parts use it, down to `SMALLEST` of that.
- **What is still crowded** after all that — an arrow that crosses another, or
  runs through a box — is returned, so it can be drawn thinner.
"""

import math
from collections.abc import Callable

Box = tuple[float, float, float, float]
Point = tuple[float, float]
Seats = dict[str, tuple[int, int]]

# How much of its slot the largest box fills, leaving arrows room between boxes.
FILL = 0.85
# The smallest box, as a fraction of the largest: still big enough for a glyph.
# Sizes grow with the square root of how many parts use a box, so the first few
# users already make a difference and one hub does not dwarf everything else.
SMALLEST = 0.6
# How heavy an arrow is drawn, against the widget's line, when the placement
# could not keep it off another arrow or a box: a lighter line over a heavier
# one reads as two arrows rather than a smudge.
THIN = 0.5
SWEEPS = 8
# What the search pays for each thing it sees in the drawing.
THROUGH = 4.0
CROSS = 1.0
LENGTH = 0.05
# A box counts as hit by an arrow a little outside its outline, where the
# arrow would still read as touching it.
MARGIN = 1.15
PASSES = 40


def _forward(names: list[str], arrows: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """The arrows left once each cycle is cut, depth-first from the busiest part."""
    out = {n: sorted(b for a, b in arrows if a == n) for n in names}
    kept: set[tuple[str, str]] = set()
    seen: set[str] = set()
    for root in sorted(names, key=lambda n: (-len(out[n]), n)):
        if root in seen:
            continue
        stack, open_ = [(root, iter(out[root]))], {root}
        seen.add(root)
        while stack:
            at, todo = stack[-1]
            nxt = next(todo, None)
            if nxt is None:
                open_.discard(at)
                stack.pop()
            elif nxt not in open_:
                kept.add((at, nxt))
                if nxt not in seen:
                    seen.add(nxt)
                    open_.add(nxt)
                    stack.append((nxt, iter(out[nxt])))
    return kept


def ranks(names: list[str], arrows: set[tuple[str, str]]) -> list[list[str]]:
    """The parts row by row, top first, each row ordered to cross the fewest arrows."""
    forward = _forward(names, arrows)
    rank = dict.fromkeys(names, 0)
    for _ in names:
        for a, b in forward:
            rank[b] = max(rank[b], rank[a] + 1)
    rows: list[list[str]] = [[] for _ in range(max(rank.values(), default=0) + 1)]
    for n in sorted(names):
        rows[rank[n]].append(n)
    near = {n: [b for a, b in arrows if a == n] + [a for a, b in arrows if b == n] for n in names}
    for sweep in range(SWEEPS):
        order = range(1, len(rows)) if sweep % 2 == 0 else range(len(rows) - 2, -1, -1)
        for r in order:
            seat = {n: i / max(1, len(row) - 1) for row in rows for i, n in enumerate(row)}
            fixed = rows[r - 1] if sweep % 2 == 0 else rows[r + 1]

            def centre(n: str, fixed: list[str] = fixed, seat: dict = seat) -> float:
                """Where this part's neighbours in the settled row sit, on average."""
                around = [seat[m] for m in near[n] if m in fixed]
                return sum(around) / len(around) if around else seat[n]

            rows[r].sort(key=lambda n: (centre(n), n))
    return rows


def place(
    names: list[str],
    arrows: set[tuple[str, str]],
    aspect: float,
    top: float = 0.0,
    used_by: dict[str, int] | None = None,
) -> tuple[dict[str, Box], set[tuple[str, str]]]:
    """A box for every part, and the arrows still crowded once they are placed.

    `aspect` is the widget's width over its height, in board cells, which are
    square on screen — so the drawing is worked out in a space `aspect` wide and
    1 tall, where a distance means the same either way. `top` is a strip left
    empty above the rows, for the widget's title. `used_by` is how many parts
    use each one, which sizes its box. Crowded arrows come back as sorted pairs.
    """
    rows = ranks(names, arrows)
    slots = max(len(row) for row in rows)
    tall = 1 - top
    largest = FILL * min(tall / len(rows), aspect / slots)
    most = max((used_by or {}).values(), default=0) or 1
    share = {n: math.sqrt((used_by or {}).get(n, 0) / most) for n in names}
    side = {n: largest * (SMALLEST + (1 - SMALLEST) * share[n]) for n in names}

    def centre(seat: tuple[int, int]) -> Point:
        """Where a seat's middle is, `aspect` wide by 1 tall."""
        return (seat[1] + 0.5) / slots * aspect, top + tall * (seat[0] + 0.5) / len(rows)

    seats: Seats = {}
    for r, row in enumerate(rows):
        for i, n in enumerate(row):
            seats[n] = (r, (slots - len(row)) // 2 + i)
    edges = sorted({(min(a, b), max(a, b)) for a, b in arrows})
    seats = _search(seats, slots, edges, side, centre)
    at = {n: centre(seat) for n, seat in seats.items()}
    boxes = {
        n: (
            _floor((x - side[n] / 2) / aspect),
            _floor(y - side[n] / 2),
            _floor(side[n] / aspect),
            _floor(side[n]),
        )
        for n, (x, y) in at.items()
    }
    return boxes, _crowded(at, edges, side)


def _search(
    seats: Seats,
    slots: int,
    edges: list[tuple[str, str]],
    side: dict[str, float],
    centre: Callable[[tuple[int, int]], Point],
) -> Seats:
    """Swap and move boxes within their rows while the drawing gets cheaper."""
    best = _cost({n: centre(s) for n, s in seats.items()}, edges, side)
    for _ in range(PASSES):
        better = False
        for n in sorted(seats):
            row, here = seats[n]
            for slot in range(slots):
                if slot == here:
                    continue
                other = next((m for m, s in seats.items() if s == (row, slot)), None)
                trial = dict(seats)
                trial[n] = (row, slot)
                if other is not None:
                    trial[other] = (row, here)
                cost = _cost({m: centre(s) for m, s in trial.items()}, edges, side)
                if cost < best - 1e-9:
                    seats, best, here, better = trial, cost, slot, True
        if not better:
            break
    return seats


def _cost(at: dict[str, Point], edges: list[tuple[str, str]], side: dict[str, float]) -> float:
    """What a drawing costs: arrows through boxes, then crossings, then length."""
    cost = 0.0
    for i, (a, b) in enumerate(edges):
        cost += LENGTH * math.dist(at[a], at[b])
        cost += THROUGH * sum(
            1 for n in at if n not in (a, b) and _hits(at[a], at[b], at[n], side[n])
        )
        for c, d in edges[i + 1 :]:
            if len({a, b, c, d}) == 4 and _cross(at[a], at[b], at[c], at[d]):
                cost += CROSS
    return cost


def _crowded(
    at: dict[str, Point], edges: list[tuple[str, str]], side: dict[str, float]
) -> set[tuple[str, str]]:
    """The arrows that still cross another or run through a box."""
    crowded = set()
    for a, b in edges:
        through = any(n not in (a, b) and _hits(at[a], at[b], at[n], side[n]) for n in at)
        crossed = any(
            len({a, b, c, d}) == 4 and _cross(at[a], at[b], at[c], at[d]) for c, d in edges
        )
        if through or crossed:
            crowded.add((a, b))
    return crowded


def _turn(p: Point, q: Point, r: Point) -> float:
    """Which way p → q → r turns: positive left, negative right, zero straight."""
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def _cross(p: Point, q: Point, r: Point, s: Point) -> bool:
    """Whether segment pq crosses segment rs, each end strictly on either side."""
    return _turn(p, q, r) * _turn(p, q, s) < 0 and _turn(r, s, p) * _turn(r, s, q) < 0


def _hits(p: Point, q: Point, middle: Point, side: float) -> bool:
    """Whether segment pq passes through the square of this side around `middle`.

    Liang-Barsky: clip the segment's parameter range against each pair of
    edges, and see whether anything is left.
    """
    half = side / 2 * MARGIN
    low, high = 0.0, 1.0
    for start, delta, centre in ((p[0], q[0] - p[0], middle[0]), (p[1], q[1] - p[1], middle[1])):
        if abs(delta) < 1e-12:
            if abs(start - centre) > half:
                return False
            continue
        t1, t2 = (centre - half - start) / delta, (centre + half - start) / delta
        low, high = max(low, min(t1, t2)), min(high, max(t1, t2))
    return low < high


def _floor(value: float) -> float:
    """Four decimals, rounded down, so a far edge never lands past 1."""
    return math.floor(value * 10_000) / 10_000
