# The single task runner, and the only place a gate lives.
#
# There is no CI. GitHub Actions was removed because it re-ran, on the owner's
# minutes, exactly what `make check` already runs — so what enforces these is the
# git hooks in `.githooks`, installed once with `make hooks`. A gate that is not
# a target here does not exist, and one no hook calls only exists when somebody
# remembers it.
#
#   make gate     fast. Every linter, no type check, no build, no test. ~9s.
#                 What `pre-commit` runs, so it has to stay quick enough that
#                 nobody reaches for --no-verify.
#   make check    everything, ~45s. What `pre-push` runs, and what has to be
#                 green before anything leaves this machine.
#
# The interpreter finds itself: this tree's venv, else the main checkout's, else
# whatever python3.12 is on PATH. A hook has no way to be told, and a person
# should not have to remember a flag to run their own gates.
#
# The second place is not a nicety. Work here happens in worktrees, a worktree
# has no `.venv` of its own, and the hooks are shared across all of them — so
# without this the first commit from any new worktree is refused by a gate that
# cannot find ruff. Which is exactly how this line came to be written.
MAIN := $(shell git rev-parse --path-format=absolute --git-common-dir 2>/dev/null | sed 's|/\.git$$||')
PYTHON ?= $(shell for p in "$(CURDIR)/backend/.venv/bin/python" "$(MAIN)/backend/.venv/bin/python"; \
            do test -x "$$p" && echo "$$p" && exit 0; done; echo python3.12)
BUN    ?= bun

.DEFAULT_GOAL := check

# ---------------------------------------------------------------------------
# Aggregate gates
# ---------------------------------------------------------------------------
.PHONY: check gate hooks backend agent frontend
check: backend agent frontend

# Fast enough to run on every commit: what a linter can say without compiling,
# building or executing anything. The type check lives in `check` rather than
# here because it costs more than the rest of this target put together.
gate: back-lint agent-lint front-quick

hooks:
	git config core.hooksPath .githooks
	@echo "hooks on: pre-commit runs 'make gate', pre-push runs 'make check'"

backend: back-lint back-types back-build back-test
agent:   agent-lint
frontend: front-lint front-dead front-build front-theme front-test

# ---------------------------------------------------------------------------
# Backend gates  (run from backend/, driven by $(PYTHON))
# ---------------------------------------------------------------------------
.PHONY: back-lint back-types back-build back-test back-install
back-lint:
	cd backend && $(PYTHON) -m ruff check .
	cd backend && $(PYTHON) -m ruff format --check .
	cd backend && $(PYTHON) lint/house_lint.py .

# The annotations are already required by ruff's ANN rules; this is what checks
# they are true. Not in `gate` — it is the second most expensive thing here, and
# a wrong annotation is not something a commit needs stopping for.
back-types:
	cd backend && $(PYTHON) -m mypy

back-build:
	cd backend && $(PYTHON) -c "import main"

back-test:
	cd backend && $(PYTHON) -m pytest

back-install:
	cd backend && python3.12 -m venv .venv
	cd backend && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# ---------------------------------------------------------------------------
# Agent gate  (tools/, the process on the host that feeds the panels)
#
# `tools/` is not part of the backend package — it is standard library only, so
# cron or a systemd unit can run it with no virtualenv — but it is Python this
# project ships, and it used to be outside every gate here. A gate that passes
# without looking is the same failure as a gate nobody runs.
#
# The backend's ruff settings are passed explicitly with --config, because ruff
# looks for configuration next to the files it is reading and there is none out
# here. One config, so the two trees cannot drift into different rules.
#
# There is no agent-test: the tests are `backend/tests/agent/` and run under
# back-test, which is the one pytest this project has. What they test is the
# half of a collector that can be tested anywhere — given this text from
# /proc, or this JSON from `gh`, produce these rows.
# ---------------------------------------------------------------------------
.PHONY: agent-lint
agent-lint:
	cd backend && $(PYTHON) -m ruff check --config pyproject.toml ../tools
	cd backend && $(PYTHON) -m ruff format --check --config pyproject.toml ../tools
	cd backend && $(PYTHON) lint/house_lint.py ../tools

# ---------------------------------------------------------------------------
# Frontend gates  (run from frontend/, driven by $(BUN))
# ---------------------------------------------------------------------------
.PHONY: front-lint front-quick front-dead front-build front-theme front-test front-install
front-lint:
	cd frontend && $(BUN) run check

# The same linters without `tsc`, which is over half of what front-lint costs.
front-quick:
	cd frontend && $(BUN) run lint

# Unused files, unused dependencies, and imports that do not resolve. Not
# unused *exports*: `lib/schemas/` mirrors the backend on purpose and
# `components/ui/` is a vendored primitive library, so most of what knip finds
# there is deliberate. A gate that has to be argued with is one that gets
# switched off — `bun run dead` shows the exports for whoever wants to look.
front-dead:
	cd frontend && $(BUN) run dead

front-build:
	cd frontend && $(BUN) run build

# Reads the built stylesheet, not the source. Tailwind emits only the theme
# variables it sees a class using, and the board takes colour names over the
# wire — so a name the backend accepts can be one the build dropped, which the
# browser resolves to nothing and paints black. Runs after front-build for the
# obvious reason: there is no artefact to read before it.
front-theme:
	cd frontend && $(BUN) run check-theme

front-test:
	cd frontend && $(BUN) run test

front-install:
	cd frontend && $(BUN) install
