#!/usr/bin/env python3
"""The high-level architecture of a Rust checkout, as JSON for a flow widget.

One box per part and one arrow per *uses*, read from what the compiler reads,
so nothing here is guessed:

- **Several local crates** (path dependencies between them, any workspace in
  the tree included): the parts are crates, and an arrow is a `path = ...`
  entry in a crate's `[dependencies]`. This is the graph cargo builds.
- **One crate**: the parts are its top-level modules, the directories under
  `src/`, and an arrow is a file in one that says `crate::<other>` outside a
  comment and before `#[cfg(test)]`.

Tried before this and rejected: a code-graph tool that links calls by name
drew crate edges cargo does not have. `use crate::x` and `path = "../x"` are
not inferences, which is the whole point.

The graph is then **transitively reduced**: an arrow that another path already
implies is dropped, so `api → scene → components` does not also draw
`api → components`. Cycles survive as cycles, and a mutual pair is one arrow
with a head at each end, which is how a cycle shows on the board.

Every box is an icon and no words: a keyword table maps a part's name to a
lucide glyph vendored beside this file (ISC, see `rust_icons/LICENSE`). A name
the table does not know gets a plain box, and is named on stderr so the table
can grow.

    rust_architecture.py ~/Desktop/Repos/scorsese --skip golden
"""

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

from rust_layout import THIN, place

ICONS = Path(__file__).resolve().parent / "rust_icons"

# A part's name, or one `_`/`-` word of it, to the lucide glyph that says what
# it is. Whole names come first because some carry no meaning a word can find:
# `zimmer` is scorsese's synthesiser, `shadergen` is not two words.
GLYPHS = {
    "zimmer": "audio-waveform",
    "shadergen": "sparkles",
    "procgen": "dices",
    "ecs": "boxes",
    "mcp": "bot",
    "api": "plug",
    "app": "app-window",
    "asset": "package",
    "assets": "package",
    "audio": "volume-2",
    "sound": "volume-2",
    "cli": "terminal",
    "shell": "terminal",
    "components": "puzzle",
    "compositor": "layers",
    "config": "settings",
    "core": "atom",
    "db": "database",
    "storage": "database",
    "dev": "wrench",
    "util": "wrench",
    "utils": "wrench",
    "editor": "pen-tool",
    "input": "gamepad-2",
    "math": "sigma",
    "navigation": "compass",
    "net": "network",
    "network": "network",
    "physics": "orbit",
    "preview": "eye",
    "providers": "cloud",
    "render": "monitor",
    "gfx": "monitor",
    "scene": "mountain",
    "scripting": "code",
    "script": "code",
    "server": "server",
    "time": "clock",
    "ui": "layout-dashboard",
}
FALLBACK = "box"

# The strip over the boxes a title needs, as a fraction of the widget's height.
# The heading is sized against the widget's width and capped, which on these
# square-ish widgets comes to about 8% of the height; 10% leaves it a margin.
TITLE_ROOM = 0.1

# Directories nobody's architecture lives in: build output, vendored packages,
# and anything hidden — a `.claude/worktrees` checkout is a second copy of the
# same crates, not more of them.
SKIPPED_DIRS = {"target", "node_modules"}

Graph = dict[str, dict[str, int]]


def manifests(root: Path) -> list[Path]:
    """Every Cargo.toml under the checkout, outside build output and hidden dirs."""
    found = []
    for path in sorted(root.rglob("Cargo.toml")):
        parts = path.relative_to(root).parts[:-1]
        if not any(p in SKIPPED_DIRS or p.startswith(".") for p in parts):
            found.append(path)
    return found


def _dependency_tables(manifest: dict) -> list[dict]:
    """The tables whose entries ship: `[dependencies]` and its per-target copies.

    Dev- and build-dependencies are left out on purpose. A crate that only a
    test uses is not part of what the program is made of.
    """
    tables = [manifest.get("dependencies", {})]
    tables += [t.get("dependencies", {}) for t in manifest.get("target", {}).values()]
    return tables


def crates(root: Path, skip: set[str]) -> Graph:
    """Crate → the local crates it depends on, named by their directories.

    Only crates joined to another by a path dependency are drawn; a crate on its
    own, a tool beside the project, has no place in a picture of how the parts
    fit. A dependency inherited with `workspace = true` is looked up in the
    nearest workspace above the crate, the way cargo does.
    """
    read = {path.parent.resolve(): tomllib.loads(path.read_text()) for path in manifests(root)}
    shared: dict[Path, dict] = {
        where: m["workspace"].get("dependencies", {})
        for where, m in read.items()
        if "workspace" in m
    }
    packages = {where: where.name for where, m in read.items() if "package" in m}
    packages = {where: name for where, name in packages.items() if name not in skip}

    graph: Graph = {}
    for where, name in packages.items():
        workspace = next((w for w in (where, *where.parents) if w in shared), None)
        for table in _dependency_tables(read[where]):
            for dep, spec in table.items():
                base = where
                if isinstance(spec, dict) and spec.get("workspace") and workspace:
                    spec, base = shared[workspace].get(dep, {}), workspace
                if not isinstance(spec, dict) or "path" not in spec:
                    continue
                used = packages.get((base / spec["path"]).resolve())
                if used and used != name:
                    graph.setdefault(name, {})[used] = 1
                    graph.setdefault(used, {})
    return graph


def _named_after(text: str, at: int) -> list[str]:
    """The first name of each path in a `crate::{a::b, c}` group starting at `at`."""
    depth, start, names = 0, at, []
    for i in range(at, len(text)):
        if text[i] == "{":
            depth += 1
            if depth == 1:
                start = i + 1
        elif text[i] in ",}" and depth == 1:
            word = re.match(r"\s*(\w+)", text[start:i])
            if word:
                names.append(word.group(1))
            start = i + 1
        if text[i] == "}":
            depth -= 1
            if depth == 0:
                break
    return names


def uses(source: str) -> set[str]:
    """The top-level names a file reaches through `crate::`, outside tests and comments.

    Everything after `#[cfg(test)]` is left out, and so is every line that is a
    comment — a doc comment saying "see `crate::render`" is not a dependency.
    """
    lines = []
    for line in source.splitlines():
        if line.strip().startswith("#[cfg(test)]"):
            break
        if not line.strip().startswith("//"):
            lines.append(line)
    text = "\n".join(lines)
    names = set(re.findall(r"\bcrate::(\w+)", text))
    for group in re.finditer(r"\bcrate::\{", text):
        names.update(_named_after(text, group.end() - 1))
    return names


def modules(root: Path, skip: set[str]) -> Graph:
    """Top-level module → the other top-level modules its files use.

    The weight of an arrow is how many files say it, kept so a threshold can be
    tried later; nothing reads it yet but the reduction's choice of which arrow
    stands for a pair.
    """
    src = root / "src"
    names = {d.name for d in src.iterdir() if d.is_dir() and d.name != "bin"} - skip
    graph: Graph = {name: {} for name in names}
    for name in names:
        for path in sorted((src / name).rglob("*.rs")):
            if "test" in path.name:
                continue
            for used in uses(path.read_text(errors="replace")) & names - {name}:
                graph[name][used] = graph[name].get(used, 0) + 1
    return graph


def components(graph: Graph) -> list[set[str]]:
    """The strongly connected components, each a set of parts that reach each other."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    found: list[set[str]] = []

    def visit(node: str) -> None:
        index[node] = low[node] = len(index)
        stack.append(node)
        for nxt in sorted(graph[node]):
            if nxt not in index:
                visit(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in stack:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            group = set()
            while True:
                top = stack.pop()
                group.add(top)
                if top == node:
                    break
            found.append(group)

    for node in sorted(graph):
        if node not in index:
            visit(node)
    return found


def _reaches[T](edges: set[tuple[T, T]], start: T, goal: T) -> bool:
    """Whether `goal` can be walked to from `start` along `edges`."""
    seen, todo = {start}, [start]
    while todo:
        at = todo.pop()
        for a, b in edges:
            if a == at and b not in seen:
                if b == goal:
                    return True
                seen.add(b)
                todo.append(b)
    return False


def reduce(graph: Graph) -> set[tuple[str, str]]:
    """The fewest arrows that say everything the graph says about who reaches whom.

    Between components it is the textbook transitive reduction of the
    condensation, and each surviving component-to-component arrow is drawn as
    the heaviest real arrow between them. Inside a component every arrow is
    tried for removal, lightest first, and goes if the component still reaches
    itself all the way round without it, so a cycle is left as a cycle.
    """
    groups = components(graph)
    owner = {node: i for i, group in enumerate(groups) for node in group}
    edges = {(a, b) for a in graph for b in graph[a]}

    between: dict[tuple[int, int], tuple[str, str]] = {}
    for a, b in sorted(edges, key=lambda e: (-graph[e[0]][e[1]], e)):
        pair = (owner[a], owner[b])
        if pair[0] != pair[1]:
            between.setdefault(pair, (a, b))
    kept = {between[(x, y)] for (x, y) in between if not _reaches(set(between) - {(x, y)}, x, y)}

    inside = {(a, b) for a, b in edges if owner[a] == owner[b]}
    for a, b in sorted(inside, key=lambda e: (graph[e[0]][e[1]], e)):
        if _reaches(inside - {(a, b)}, a, b):
            inside.discard((a, b))
    return kept | inside


def glyph(name: str, missed: list[str]) -> str:
    """The SVG for a part, by whole name, then by its first known word."""
    words = [name, *re.split(r"[_-]", name)]
    icon = next((GLYPHS[w] for w in words if w in GLYPHS), None)
    if icon is None:
        missed.append(name)
    return (ICONS / f"{icon or FALLBACK}.svg").read_text().strip()


def flow(graph: Graph, aspect: float | None = None, title: str | None = None) -> dict:
    """The graph as a flow payload: icon boxes, and arrows with a mutual pair merged.

    Given the widget's `aspect` (width over height, in board cells) every box is
    placed, square, by `rust_layout`; without it the widget lays them out. A
    `title` is the project's name over the diagram, and the boxes start below it.
    """
    arrows = reduce(graph)
    missed: list[str] = []
    nodes: list[dict] = [{"id": name, "icon": glyph(name, missed)} for name in sorted(graph)]
    crowded: set[tuple[str, str]] = set()
    if aspect:
        used_by = {name: sum(name in uses for uses in graph.values()) for name in graph}
        top = TITLE_ROOM if title else 0.0
        boxes, crowded = place(sorted(graph), arrows, aspect, top, used_by)
        for node in nodes:
            node.update(zip("xywh", boxes[node["id"]], strict=True))
    links: list[dict] = []
    for a, b in sorted(arrows):
        if (b, a) in arrows and a > b:
            continue
        link: dict = {"source": a, "target": b}
        if (b, a) in arrows:
            link["heads"] = "both"
        if (min(a, b), max(a, b)) in crowded:
            link["thickness"] = THIN
        links.append(link)
    if missed:
        print(f"rust_architecture: no icon for {', '.join(missed)}", file=sys.stderr)
    return {"title": title, "nodes": nodes, "links": links}


def read(root: Path, skip: set[str]) -> Graph:
    """Crates when the checkout has several joined by path, else one crate's modules."""
    graph = crates(root, skip)
    return graph if len(graph) > 1 else modules(root, skip)


def main() -> int:
    """Print the architecture of the checkout given on the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="a local checkout")
    parser.add_argument("--skip", default="", help="comma-separated parts to leave out")
    parser.add_argument(
        "--aspect", type=float, help="the widget's width over its height, to place the boxes"
    )
    parser.add_argument("--title", help="the name drawn over the diagram")
    args = parser.parse_args()
    skip = set(filter(None, args.skip.split(",")))
    print(json.dumps(flow(read(args.root.expanduser(), skip), args.aspect, args.title)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
