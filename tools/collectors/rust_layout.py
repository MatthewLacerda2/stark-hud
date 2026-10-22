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
  boxes under their neighbours rather than spread out — or **one more**, when
  the spare column lets arrows go round boxes they would otherwise run through.
  It costs every box a little size, so it is taken only when the drawing comes
  out cheaper with it. Which box takes which seat starts from the barycentre
  heuristic and is then improved by looking at the drawing itself: every
  seating of one row is tried while the others stand still (or, in a row too
  busy to try them all, every swap and every move to a free seat), row after
  row until nothing improves. An arrow through a box costs most, since it reads
  as a dependency that is not there; a crossing next; length only breaks ties.
  Moving one box at a time was tried first and stopped at a drawing with two
  arrows through boxes where a whole row's reshuffle had none. Deterministic:
  the same graph draws the same picture every hour.
- **A box is a card**: a glyph's square, square at the widget's shape (hence
  `aspect`), over a strip for the part's name. The square is as large as the
  busiest row and the number of rows allow — for the part that most others use
  — and shrinks with how few parts use it, down to `SMALLEST` of that. The
  strip is one height on every card, so every name is written the same size: a
  name that shrank with its box made the parts few others use unreadable.
- **Arrows are scored where they are drawn**, between the midpoints of the
  sides two boxes face each other across, the rule `facing()` in the widget's
  `frontend/src/lib/flow.ts` follows. Measured from the middles instead, two
  arrows out of one side looked apart to the search and were one line on the
  board. Two arrows leaving or reaching one point at nearly the same angle are
  charged as much as an arrow through a box: they read as one arrow, which is
  the same lie told the other way round.
- **What is still crowded** after all that — an arrow that crosses another,
  runs through a box or lies along another — is returned, so it can be drawn
  thinner.
"""

import itertools
import math
from collections.abc import Callable, Iterator

Box = tuple[float, float, float, float]
Point = tuple[float, float]
Seats = dict[str, tuple[int, int]]
# Half a box's width and half its height, in the `aspect`-wide drawing space.
Half = tuple[float, float]
Edge = tuple[str, str]

# How much of its slot the largest box fills, leaving arrows room between boxes.
FILL = 0.85
# The smallest box, as a fraction of the largest: still big enough for a glyph.
# Sizes grow with the square root of how many parts use a box, so the first few
# users already make a difference and one hub does not dwarf everything else.
SMALLEST = 0.6
# The strip under a glyph that holds the part's name, as a fraction of the
# largest glyph's side: enough for one line of a name at a size that reads.
NAME = 0.3
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
# Two arrows out of one point closer than this, in degrees, are drawn as one.
ALONG = 12.0
PASSES = 40
# The most seatings of one row the search tries outright; past this it swaps.
SEATINGS = 5_000


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
    arrows: set[Edge],
    aspect: float,
    top: float = 0.0,
    used_by: dict[str, int] | None = None,
) -> tuple[dict[str, Box], set[Edge]]:
    """A card for every part, and the arrows still crowded once they are placed.

    `aspect` is the widget's width over its height, in board cells, which are
    square on screen — so the drawing is worked out in a space `aspect` wide and
    1 tall, where a distance means the same either way. `top` is a strip left
    empty above the rows, for the widget's title. `used_by` is how many parts
    use each one, which sizes its card: the glyph's square, with the name's
    strip under it. Crowded arrows come back as sorted pairs.
    """
    rows = ranks(names, arrows)
    busiest = max(len(row) for row in rows)
    edges = sorted({(min(a, b), max(a, b)) for a, b in arrows})
    drawings = [_draw(rows, n, edges, aspect, top, used_by) for n in (busiest, busiest + 1)]
    _, at, half = min(drawings, key=lambda drawing: drawing[0])
    boxes = {
        n: (
            _floor((x - half[n][0]) / aspect),
            _floor(y - half[n][1]),
            _floor(2 * half[n][0] / aspect),
            _floor(2 * half[n][1]),
        )
        for n, (x, y) in at.items()
    }
    return boxes, _crowded(at, edges, half)


def _draw(
    rows: list[list[str]],
    slots: int,
    edges: list[Edge],
    aspect: float,
    top: float,
    used_by: dict[str, int] | None,
) -> tuple[float, dict[str, Point], dict[str, Half]]:
    """The cheapest drawing with this many seats a row: its cost, middles and box sizes."""
    names = [n for row in rows for n in row]
    tall = 1 - top
    largest = FILL * min(tall / len(rows) / (1 + NAME), aspect / slots)
    strip = NAME * largest
    most = max((used_by or {}).values(), default=0) or 1
    share = {n: math.sqrt((used_by or {}).get(n, 0) / most) for n in names}
    side = {n: largest * (SMALLEST + (1 - SMALLEST) * share[n]) for n in names}
    half = {n: (side[n] / 2, (side[n] + strip) / 2) for n in names}

    def centre(seat: tuple[int, int]) -> Point:
        """Where a seat's middle is, `aspect` wide by 1 tall."""
        return (seat[1] + 0.5) / slots * aspect, top + tall * (seat[0] + 0.5) / len(rows)

    seats: Seats = {}
    for r, row in enumerate(rows):
        for i, n in enumerate(row):
            seats[n] = (r, (slots - len(row)) // 2 + i)
    seats = _search(seats, rows, slots, lambda s: _cost(_middles(s, centre), edges, half))
    at = _middles(seats, centre)
    return _cost(at, edges, half), at, half


def _middles(seats: Seats, centre: Callable[[tuple[int, int]], Point]) -> dict[str, Point]:
    """Where each box's middle is, from its seat."""
    return {n: centre(seat) for n, seat in seats.items()}


def _search(
    seats: Seats, rows: list[list[str]], slots: int, cost: Callable[[Seats], float]
) -> Seats:
    """Reseat one row at a time, the others standing still, while the drawing gets cheaper."""
    best = cost(seats)
    for _ in range(PASSES):
        better = False
        for r, row in enumerate(rows):
            for trial in _seatings(seats, r, row, slots):
                price = cost(trial)
                if price < best - 1e-9:
                    seats, best, better = trial, price, True
        if not better:
            break
    return seats


def _seatings(seats: Seats, r: int, row: list[str], slots: int) -> Iterator[Seats]:
    """Every seating of one row, or every swap and move in a row too busy for that."""
    if math.perm(slots, len(row)) <= SEATINGS:
        for chosen in itertools.permutations(range(slots), len(row)):
            yield {**seats, **{n: (r, slot) for n, slot in zip(row, chosen, strict=True)}}
        return
    for n in row:
        here = seats[n][1]
        for slot in range(slots):
            other = next((m for m in row if seats[m][1] == slot), None)
            if slot != here:
                trial = {**seats, n: (r, slot)}
                if other is not None:
                    trial[other] = (r, here)
                yield trial


def ends(at: dict[str, Point], half: dict[str, Half], a: str, b: str) -> tuple[Point, Point]:
    """Where the arrow between two boxes is drawn: the facing sides' midpoints.

    Whichever axis their middles are further apart on, as the widget decides it.
    """
    (ax, ay), (bx, by) = at[a], at[b]
    if abs(bx - ax) >= abs(by - ay):
        sign = 1 if bx >= ax else -1
        return (ax + sign * half[a][0], ay), (bx - sign * half[b][0], by)
    sign = 1 if by >= ay else -1
    return (ax, ay + sign * half[a][1]), (bx, by - sign * half[b][1])


def _faults(at: dict[str, Point], edges: list[Edge], half: dict[str, Half]) -> list[list[str]]:
    """What is wrong with each arrow as drawn: boxes it runs through, crossings, twins."""
    drawn = {e: ends(at, half, *e) for e in edges}
    faults: list[list[str]] = [[] for _ in edges]
    for i, (a, b) in enumerate(edges):
        p, q = drawn[(a, b)]
        faults[i] += ["through"] * sum(
            1 for n in at if n not in (a, b) and hits(p, q, at[n], half[n])
        )
        for j in range(i + 1, len(edges)):
            r, s = drawn[edges[j]]
            if len({a, b, *edges[j]}) == 4 and _cross(p, q, r, s):
                faults[i].append("cross")
                faults[j].append("cross")
            elif along(p, q, r, s):
                faults[i].append("along")
                faults[j].append("along")
    return faults


def _cost(at: dict[str, Point], edges: list[Edge], half: dict[str, Half]) -> float:
    """What a drawing costs: arrows through boxes or along each other, crossings, length."""
    price = {"through": THROUGH, "along": THROUGH / 2, "cross": CROSS / 2}
    cost = sum(LENGTH * math.dist(*ends(at, half, a, b)) for a, b in edges)
    return cost + sum(price[f] for found in _faults(at, edges, half) for f in found)


def _crowded(at: dict[str, Point], edges: list[Edge], half: dict[str, Half]) -> set[Edge]:
    """The arrows that still cross another, run through a box or lie along another."""
    return {edge for edge, found in zip(edges, _faults(at, edges, half), strict=True) if found}


def along(p: Point, q: Point, r: Point, s: Point) -> bool:
    """Whether two arrows leave or reach one point at nearly the same angle."""
    return any(
        math.dist(here, end) < 1e-9 and _angle(here, there, other) < ALONG
        for here, there in ((p, q), (q, p))
        for end, other in ((r, s), (s, r))
    )


def _angle(at: Point, a: Point, b: Point) -> float:
    """The angle at `at` between the lines out to `a` and to `b`, in degrees."""
    turn = math.atan2(a[1] - at[1], a[0] - at[0]) - math.atan2(b[1] - at[1], b[0] - at[0])
    return math.degrees(abs((turn + math.pi) % (2 * math.pi) - math.pi))


def _turn(p: Point, q: Point, r: Point) -> float:
    """Which way p → q → r turns: positive left, negative right, zero straight."""
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def _cross(p: Point, q: Point, r: Point, s: Point) -> bool:
    """Whether segment pq crosses segment rs, each end strictly on either side."""
    return _turn(p, q, r) * _turn(p, q, s) < 0 and _turn(r, s, p) * _turn(r, s, q) < 0


def hits(p: Point, q: Point, middle: Point, half: Half) -> bool:
    """Whether segment pq passes through the box of this half-size around `middle`.

    Liang-Barsky: clip the segment's parameter range against each pair of
    edges, and see whether anything is left.
    """
    low, high = 0.0, 1.0
    for start, delta, centre, reach in (
        (p[0], q[0] - p[0], middle[0], half[0] * MARGIN),
        (p[1], q[1] - p[1], middle[1], half[1] * MARGIN),
    ):
        if abs(delta) < 1e-12:
            if abs(start - centre) > reach:
                return False
            continue
        t1, t2 = (centre - reach - start) / delta, (centre + reach - start) / delta
        low, high = max(low, min(t1, t2)), min(high, max(t1, t2))
    return low < high


def _floor(value: float) -> float:
    """Four decimals, rounded down, so a far edge never lands past 1."""
    return math.floor(value * 10_000) / 10_000
