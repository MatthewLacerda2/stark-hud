# Backend

FastAPI + Pydantic, organized as a strict layered stack. The root `CLAUDE.md`
governs how we work; this file governs how this package is built.

## Layers

`api/` (handlers) → `schemas/` (Pydantic I/O) → `services/` (rules) →
`repositories/` (state).

- **State lives only in `repositories/`.** There is no database — the board is a
  dict in `repositories/board.py` — but the boundary is kept anyway. Nothing
  outside that module reads or writes the store, so adding a `.hudtv` file later
  is a rewrite of one file and nothing else.
- **Placement rules live in `services/`.** `placement.py` decides where an item
  may sit; `board.py` composes that with the repository. Handlers stay thin.
- All request/response bodies are Pydantic models. Payloads are a discriminated
  union on `kind`, so an unknown kind is a 422 and never reaches a handler.
- Type annotations are enforced (ruff `ANN`).
- Config is `pydantic-settings`, read through `@lru_cache get_settings()`.

## The board is finite

The board is a fixed space and never scrolls, so running out of room is a normal
outcome, not an edge case. Coordinates are fractional — a widget sits where it
was put, not in the nearest of 576 squares — and nothing silently shrinks,
evicts, or overlaps: when a request does not fit, the caller gets a 409 saying
how much space is free, and decides what to do. `GET /board/status` lets a
caller look before it leaps.

## Size limits (enforced by `tools/house_lint.py`)

- File ≤ 350 lines — opt a data module out with `# lint: data-file` in the
  first 15 lines; `tests/**` is exempt.
- Endpoint handler ≤ 50 lines. Test ≤ 50 lines.

## Tests

There is no database, so there are no fixtures to speak of: `tests/conftest.py`
clears the board around every test and that is the whole of the shared state.
API tests drive the real app through `httpx.ASGITransport` with nothing mocked.

## Gate before pushing

`make backend` = `back-lint` (ruff + ruff-format + `house_lint.py`) ·
`back-build` (imports `main`) · `back-test` (pytest). Green before you push.
