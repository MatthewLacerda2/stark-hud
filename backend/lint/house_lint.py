"""Custom house linter (pure stdlib, AST-based): what to scan, and what to say.

The rules themselves are next door, in two modules that share nothing:

  `limits.py`      1. a file longer than ``MAX_FILE_LINES``,
                   2. a ``@router.<method>`` handler longer than
                      ``MAX_HANDLER_LINES``, and
                   3. a ``test_*`` function longer than ``MAX_TEST_LINES``.
  `boundaries.py`  4. an import that climbs the stack instead of descending it,
                   5. anything but ``services/events.py`` reaching the socket
                      hub, and
                   6. a surface writing to a repository instead of reading it.

They were one file until rule 1 came to apply to it honestly. The split is along
the seam that was already there: one module knows how much of a thing there is,
the other knows what the stack is, and neither has ever needed the other.

This module is importable (every rule returns a list of violations) and runnable
as ``python -m lint.house_lint`` to scan the backend tree, or with paths to scan
those instead — which is how the agent under the repository's own ``tools/``
gets looked at by the same rules. It is run with ``-m`` because it imports its
siblings by package: a script run by path puts its own directory on `sys.path`
and not the package's.

It lives in ``lint/`` and not in a ``tools/`` of its own: there is a ``tools/``
at the repository root holding the agent, and two directories with one name is
how this file came to be linting a tree it was never pointed at.
"""

from __future__ import annotations

import sys
from pathlib import Path

from lint import boundaries, limits


def check_source(path: Path, source: str, layer: str | None = None) -> list[str]:
    """Run every rule against a single file's source text."""
    return (
        limits.check_file_length(path, source)
        + limits.check_function_lengths(path, source)
        + boundaries.check_layers(path, source, layer)
        + boundaries.check_hub(path, source, layer)
        + boundaries.check_repository_writes(path, source, layer)
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
        violations.extend(check_source(path, source, boundaries.layer_of(path, root)))
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
