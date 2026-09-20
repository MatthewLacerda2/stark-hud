"""Who may reach what: rules 4, 5 and 6.

Three rules about direction rather than size — which layer may import which,
which module may talk to every connected board, and which layer may write to the
store. Each of them is the architecture stated once, somewhere a gate can read
it, instead of stated in prose and enforced by whoever remembers.

They sit apart from `limits.py` because they share nothing with it: a length
rule needs to know how many lines there are, these need to know what the stack
is, and neither has ever needed the other.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Which layer may import which, and the whole of the architecture in one dict.
#
# `api/` and `hud_mcp/` are both surfaces — one speaks HTTP and the other MCP,
# and neither is above the other. Under them `services/` holds the rules, and
# under that `repositories/` is the only place state is touched. `schemas/` and
# `core/` sit beneath everything and reach for nothing.
#
# An import going the other way is not a style question. It is the boundary
# moving, quietly, in a codebase whose entire claim is that swapping how the
# board persists is a rewrite of one module. `main.py` and `tests/` are outside
# the stack and unlisted, which is how they stay free to import anything.
LAYERS: dict[str, frozenset[str]] = {
    "api": frozenset({"core", "schemas", "services", "repositories"}),
    "hud_mcp": frozenset({"core", "schemas", "services", "repositories"}),
    "services": frozenset({"core", "schemas", "repositories"}),
    "repositories": frozenset({"core", "schemas"}),
    "schemas": frozenset({"core"}),
    "core": frozenset(),
    "lint": frozenset(),
}

# Who may reach the socket. ``core.hub`` is fan-out and nothing else, but a
# module that can reach it can announce a change — which means a module that
# forgets to is a board on a television showing the old thing and looking fine.
# Nothing checks for a missing broadcast and nothing can, so the enforceable
# half is this: the hub has one caller, the services announce their own writes,
# and a surface that wants to send an event has to go and add one there.
#
# ``main.py`` is outside the stack and unlisted, which is how it stays free to
# hold the socket itself; ``tests/`` listens on the hub to read events back.
HUB_MODULE = "core.hub"
HUB_CALLER = ("services", "events.py")

# Which layers may read the store but not write to it, and how a read is told from a write.
#
# `CLAUDE.md` used to say every surface reached the store through `services/`,
# and no surface ever did: every call is a `repo.get` fetching the widget a
# handler is about to act on, and a pass-through per read would only keep a
# sentence true. So the sentence changed, and this is the half worth enforcing:
# the boundary exists so replacing the `.hud` file stays a rewrite of one module
# — which a write threatens and a read does not.
#
# READ_PREFIXES is an allowlist, and that choice is the whole rule. A denylist
# of write-ish names (`set`, `add`, `remove`) reads the same today and fails the
# opposite way tomorrow, because the next function added to `repositories/` is
# on neither list: a denylist waves it through, an allowlist stops it. One asks a
# human to look at a new write; the other lets the boundary move in silence,
# which is how this rule came to be wrong in the first place. The cost is that a
# read named `showing()` is stopped too — a failing gate and a one-line
# decision, and the direction to be wrong in.
#
# Matching is on the first underscore-separated word, not a `startswith`, so
# `get_by_key` reads while a future `settle()` is not mistaken for one.
SURFACE_LAYERS = frozenset({"api", "hud_mcp"})
REPOSITORY_ROOT = "repositories"
READ_PREFIXES = frozenset({"get", "list", "find", "search", "count", "has", "exists"})
_WRITE_HINT = "write through services/ (a read may come straight from the repository)"


def layer_of(path: Path, root: Path) -> str | None:
    """Which layer a file belongs to, or ``None`` when it sits outside the stack.

    Worked out against the scan root rather than the path alone, because this
    linter is run both with a root (`house_lint .`) and without one, and those
    give relative and absolute paths respectively. Reading `parts[0]` would have
    quietly found no layer at all in the second case — a check that inspects
    nothing and passes, which is the failure mode this file exists to prevent.
    """
    try:
        parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        return None
    return parts[0] if parts and parts[0] in LAYERS else None


def _imported_layers(source: str) -> list[tuple[int, str]]:
    """Every layer this file imports from, with the line it was imported on."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        for name in names:
            top = name.split(".")[0]
            if top in LAYERS:
                found.append((node.lineno, top))
    return found


def check_layers(path: Path, source: str, layer: str | None) -> list[str]:
    """Rule 4: flag imports that climb the stack instead of descending it."""
    if layer is None:
        return []
    allowed = LAYERS[layer]
    return [
        f"{path}:{line}: {layer}/ imports {other}/, which is above it "
        f"({layer}/ may import: {', '.join(sorted(allowed)) or 'nothing'})"
        for line, other in _imported_layers(source)
        if other != layer and other not in allowed
    ]


def _imports_hub(source: str) -> list[int]:
    """The lines on which this file pulls in the socket hub, if any."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module == HUB_MODULE:
            found.append(node.lineno)
        elif isinstance(node, ast.Import) and any(a.name == HUB_MODULE for a in node.names):
            found.append(node.lineno)
    return found


def check_hub(path: Path, source: str, layer: str | None) -> list[str]:
    """Rule 5: keep the one module that talks to every connected board alone.

    Files outside the stack — ``main.py``, which owns the socket, and the tests,
    which listen on it — are not checked, the same as every other rule here.
    """
    if layer is None or (layer, path.name) == HUB_CALLER:
        return []
    return [
        f"{path}:{line}: {layer}/ imports {HUB_MODULE}, which only "
        f"{HUB_CALLER[0]}/{HUB_CALLER[1]} may do — announce the change from the "
        f"service that makes it, through services.events"
        for line in _imports_hub(source)
    ]


def _is_read_name(name: str) -> bool:
    """True when a repository function's name can only mean a question."""
    return name.split("_")[0] in READ_PREFIXES


def _attribute_root(node: ast.expr) -> str | None:
    """The name at the bottom of an attribute chain: ``a.b.c`` -> ``a``."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _repository_names(tree: ast.AST) -> tuple[set[str], list[tuple[int, str]]]:
    """Names bound to a repository module, and functions imported out of one.

    The house style is ``from repositories import board as repo``, which binds a
    module. ``from repositories.board import add`` binds the write itself, which
    leaves a call check nothing to see, so it is caught at the import instead.
    """
    modules: set[str] = set()
    direct: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            head, _, rest = node.module.partition(".")
            if head != REPOSITORY_ROOT:
                continue
            for alias in node.names:
                if rest:  # from repositories.board import add
                    direct.append((node.lineno, alias.name))
                else:  # from repositories import board as repo
                    modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == REPOSITORY_ROOT:
                    modules.add(alias.asname or REPOSITORY_ROOT)
    return modules, direct


def check_repository_writes(path: Path, source: str, layer: str | None) -> list[str]:
    """Rule 6: a surface may read the store, but writes go through ``services/``.

    Only the surfaces are checked. ``services/`` writes to repositories for a
    living, and ``main.py`` and the tests sit outside the stack as always.
    """
    if layer not in SURFACE_LAYERS:
        return []
    tree = ast.parse(source)
    modules, direct = _repository_names(tree)

    flagged: list[tuple[int, str]] = [
        (line, f"imports {REPOSITORY_ROOT}.{name}")
        for line, name in direct
        if not _is_read_name(name)
    ]
    for node in ast.walk(tree):  # walk order is not source order, hence the sort
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if _attribute_root(node.func) not in modules or _is_read_name(node.func.attr):
            continue
        flagged.append((node.lineno, f"calls repository '{node.func.attr}'"))
    return [
        f"{path}:{line}: {layer}/ {what}, which is not a read — {_WRITE_HINT}"
        for line, what in sorted(flagged)
    ]
