"""Custom house linter (pure stdlib, AST-based).

Rules enforced:
  1. A source file longer than ``MAX_FILE_LINES`` lines fails, unless it carries
     a ``# lint: data-file`` marker within its first 15 lines. Files under a
     ``tests/`` directory are exempt from this rule.
  2. Any function decorated with ``@router.<method>`` (get/post/put/patch/delete)
     longer than ``MAX_HANDLER_LINES`` (def line to last line, decorators
     excluded) fails.
  3. Any ``test_*`` function under a ``tests/`` directory longer than
     ``MAX_TEST_LINES`` fails.
  4. An import that crosses a layer boundary the wrong way fails. The stack runs
     one direction and `CLAUDE.md` has always said so; this is where saying it
     stops being the only enforcement.
  5. Only ``services/events.py`` may import the socket hub. Telling the
     television is part of making a change, not something a handler or a tool
     remembers afterwards — and the way that rots is one more call site typing
     one more event name.
  6. A surface may *read* a repository directly, but may not *write* to one.
     Reads skip ``services/`` on purpose; a write from a handler is the
     boundary moving.

The module is importable (rules return violation lists) and runnable as
``python lint/house_lint.py`` to scan the backend tree, or with paths to scan
those instead — which is how the agent under the repository's own ``tools/``
gets looked at by the same rules.

It lives in ``lint/`` and not in a ``tools/`` of its own: there is a ``tools/``
at the repository root holding the agent, and two directories with one name is
how this file came to be linting a tree it was never pointed at.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

MAX_FILE_LINES = 350
MAX_HANDLER_LINES = 50
MAX_TEST_LINES = 50
DATA_FILE_MARKER = "# lint: data-file"
_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})
_MARKER_SCAN_LINES = 15

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

LAYERS: dict[str, frozenset[str]] = {
    "api": frozenset({"core", "schemas", "services", "repositories"}),
    "hud_mcp": frozenset({"core", "schemas", "services", "repositories"}),
    "services": frozenset({"core", "schemas", "repositories"}),
    "repositories": frozenset({"core", "schemas"}),
    "schemas": frozenset({"core"}),
    "core": frozenset(),
    "lint": frozenset(),
}


def _is_under_tests(path: Path) -> bool:
    """Return True if any path component is a ``tests`` directory."""
    return "tests" in path.parts


def _node_line_span(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Number of lines a function spans, excluding decorators.

    Typed to the two nodes it is ever called with. `ast.AST` was wider than the
    truth and cost the caller nothing, but it also meant `.lineno` was being read
    off a base class that does not have it.
    """
    start = node.lineno  # `def`/`async def` line, after decorators
    end = node.end_lineno or start
    return end - start + 1


def _is_router_handler(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if the function is decorated with ``@router.<http-method>(...)``."""
    for dec in node.decorator_list:
        call = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(call, ast.Attribute) and call.attr in _HTTP_METHODS:
            return True
    return False


def check_file_length(path: Path, source: str) -> list[str]:
    """Rule 1: enforce the maximum file length."""
    if _is_under_tests(path):
        return []
    lines = source.splitlines()
    if len(lines) <= MAX_FILE_LINES:
        return []
    header = "\n".join(lines[:_MARKER_SCAN_LINES])
    if DATA_FILE_MARKER in header:
        return []
    return [f"{path}: file has {len(lines)} lines (max {MAX_FILE_LINES})"]


def check_function_lengths(path: Path, source: str) -> list[str]:
    """Rules 2 and 3: enforce handler and test function length limits."""
    violations: list[str] = []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"{path}: syntax error: {exc}"]

    under_tests = _is_under_tests(path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        span = _node_line_span(node)
        if _is_router_handler(node) and span > MAX_HANDLER_LINES:
            violations.append(
                f"{path}:{node.lineno}: handler '{node.name}' is {span} lines "
                f"(max {MAX_HANDLER_LINES})"
            )
        if under_tests and node.name.startswith("test_") and span > MAX_TEST_LINES:
            violations.append(
                f"{path}:{node.lineno}: test '{node.name}' is {span} lines (max {MAX_TEST_LINES})"
            )
    return violations


def layer_of(path: Path, root: Path) -> str | None:
    """Which layer a file belongs to, or ``None`` when it sits outside the stack.

    Worked out against the scan root rather than the path alone, because this
    linter is run both with a root (`house_lint.py .`) and without one, and those
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
    """Flag imports that climb the stack instead of descending it."""
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


def check_source(path: Path, source: str, layer: str | None = None) -> list[str]:
    """Run every rule against a single file's source text."""
    return (
        check_file_length(path, source)
        + check_function_lengths(path, source)
        + check_layers(path, source, layer)
        + check_hub(path, source, layer)
        + check_repository_writes(path, source, layer)
    )


def iter_python_files(root: Path) -> list[Path]:
    """Yield Python files under ``root``, skipping caches and virtualenvs."""
    skip = {".venv", "__pycache__", ".ruff_cache", ".pytest_cache", ".git"}
    return sorted(p for p in root.rglob("*.py") if not any(part in skip for part in p.parts))


def scan(root: Path) -> list[str]:
    """Scan the tree under ``root`` and return all violations."""
    violations: list[str] = []
    for path in iter_python_files(root):
        source = path.read_text(encoding="utf-8")
        violations.extend(check_source(path, source, layer_of(path, root)))
    return violations


def main(argv: list[str] | None = None) -> int:
    """Entry point: scan what was named, or the backend tree, and set exit code."""
    named = argv if argv is not None else sys.argv[1:]
    roots = [Path(a) for a in named] or [Path(__file__).resolve().parent.parent]
    violations = [v for root in roots for v in scan(root)]
    if violations:
        for v in violations:
            print(v)
        print(f"\nhouse_lint: {len(violations)} violation(s)")
        return 1
    print("house_lint: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
