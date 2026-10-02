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
- **Each row ordered to cross less**, by the mean position of its neighbours in
  the rows above and below, swept down and up a few times (the barycentre
  heuristic). Deterministic: the same graph draws the same picture every hour.
- **Square boxes**, one size for all, as large as the busiest row and the
  number of rows allow, square at the widget's shape — hence `aspect`.
"""

import math

Box = tuple[float, float, float, float]

# How much of its slot a box fills, so arrows have room between the boxes.
FILL = 0.6
SWEEPS = 8


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
    names: list[str], arrows: set[tuple[str, str]], aspect: float, top: float = 0.0
) -> dict[str, Box]:
    """A square box for every part, in rows, each row centred across the widget.

    `aspect` is the widget's width over its height, in board cells, which are
    square on screen — so a box `side` tall is `side / aspect` wide. `top` is
    a strip left empty above the rows, for the widget's title.
    """
    rows = ranks(names, arrows)
    busiest = max(len(row) for row in rows)
    tall = 1 - top
    side = FILL * min(tall / len(rows), aspect / busiest)
    placed: dict[str, Box] = {}
    for r, row in enumerate(rows):
        y = top + tall * (r + 0.5) / len(rows) - side / 2
        for i, n in enumerate(row):
            x = ((i + 0.5) / len(row)) - side / aspect / 2
            placed[n] = (_floor(x), _floor(y), _floor(side / aspect), _floor(side))
    return placed


def _floor(value: float) -> float:
    """Four decimals, rounded down, so a far edge never lands past 1."""
    return math.floor(value * 10_000) / 10_000
