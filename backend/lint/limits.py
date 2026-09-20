"""How long a thing may be: rules 1, 2 and 3.

A ceiling on a file, on a route handler and on a test. None of the three is
about what the code says, only about how much of it is in one place — which is
the part a reader pays for, and the part that grows without anybody deciding it
should.

These left ``house_lint.py`` when rule 1 came to apply to that file honestly:
the runner, the boundary rules and these together are past the ceiling they
carry, and trimming the comments to fit would have been the linter lying about
its own rule a second time.
"""

from __future__ import annotations

import ast
from pathlib import Path

MAX_FILE_LINES = 350
MAX_HANDLER_LINES = 50
MAX_TEST_LINES = 50
DATA_FILE_MARKER = "# lint: data-file"
_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})
_MARKER_SCAN_LINES = 15


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


def _carries_marker(header: list[str]) -> bool:
    """True when one of these lines *is* the marker, rather than mentions it.

    This used to be a substring search over the header text, and the linter's own
    module docstring quotes the marker while explaining what it does — so the one
    file in this repository that could not be measured for length was the file
    that measures length, and it reported ``clean`` at 354 lines. Every other
    file that ever quotes the marker in prose had the same hole.

    A marker is a line of its own. A sentence about one is prose, and prose about
    a rule is not an exemption from it.
    """
    return any(line.strip() == DATA_FILE_MARKER for line in header)


def check_file_length(path: Path, source: str) -> list[str]:
    """Rule 1: enforce the maximum file length."""
    if _is_under_tests(path):
        return []
    lines = source.splitlines()
    if len(lines) <= MAX_FILE_LINES:
        return []
    if _carries_marker(lines[:_MARKER_SCAN_LINES]):
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
