# The single task runner, and the only place a gate lives.
#
# There is no CI. GitHub Actions was removed because it re-ran, on the owner's
# minutes, exactly what `make check` already runs — so what enforces these is the
# git hooks in `.githooks`, installed once with `make hooks`. A gate that is not
# a target here does not exist, and one no hook calls only exists when somebody
# remembers it.
#
#   make gate     fast. Every linter, no type check, no build, no test, and no
#                 docker. ~9s. What `pre-commit` runs, so it has to stay quick
#                 enough that nobody reaches for --no-verify.
#   make check    everything, ~45s. What `pre-push` runs, and what has to be
#                 green before anything leaves this machine. The container
#                 build it now ends on costs a second or so, cached.
#
# One Python, named once. The agent in `tools/` runs under the host's system
# python, the backend runs in a container, and the gates run in a venv — and a
# gate only means something if all three are the same interpreter. This is the
# line to edit to move the project; `py-version` refuses the two files that
# cannot read a Makefile until they agree with it.
PYTHON_VERSION := 3.14

# The interpreter finds itself: this tree's venv, else the main checkout's, else
# whatever `python$(PYTHON_VERSION)` is on PATH. A hook has no way to be told,
# and a person should not have to remember a flag to run their own gates.
#
# The second place is not a nicety. Work here happens in worktrees, a worktree
# has no `.venv` of its own, and the hooks are shared across all of them — so
# without this the first commit from any new worktree is refused by a gate that
# cannot find ruff. Which is exactly how this line came to be written.
MAIN := $(shell git rev-parse --path-format=absolute --git-common-dir 2>/dev/null | sed 's|/\.git$$||')
PYTHON ?= $(shell for p in "$(CURDIR)/backend/.venv/bin/python" "$(MAIN)/backend/.venv/bin/python"; \
            do test -x "$$p" && echo "$$p" && exit 0; done; echo python$(PYTHON_VERSION))
BUN    ?= bun

.DEFAULT_GOAL := check

# ---------------------------------------------------------------------------
# Aggregate gates
# ---------------------------------------------------------------------------
.PHONY: check gate hooks backend agent frontend
check: backend agent frontend

# Fast enough to run on every commit: what a linter can say without compiling,
# building or executing anything, plus `py-version`, which is two greps. The
# type check lives in `check` rather than here because it costs more than the
# rest of this target put together, and the container build lives there because
# it is the one gate that needs a docker daemon — pre-commit has to work on a
# machine where the daemon is not up.
gate: py-version back-lint agent-lint front-quick

hooks:
	git config core.hooksPath .githooks
	@echo "hooks on: pre-commit runs 'make gate', pre-push runs 'make check'"

backend: py-version back-lint back-types back-test back-build
agent:   agent-lint agent-types
frontend: front-lint front-dead front-build front-theme front-test

# ---------------------------------------------------------------------------
# One Python  (PYTHON_VERSION, wherever it is spelled a second time)
#
# Two files cannot read a variable out of a Makefile: ruff's target-version in
# `backend/pyproject.toml`, and the base image in `backend/Dockerfile`, whose
# FROM line is read before any file in the build context exists. So they are
# checked rather than derived — edit PYTHON_VERSION and this names the one that
# was left behind, which is cheaper than hearing it from a container.
#
# The third check is the point of the exercise. The venv is not in git, so
# after a version bump it stays whatever it was when it was made, and a gate
# quietly running on last year's interpreter is a gate describing a program
# nobody runs. mypy has no `python_version` for the same reason: it follows
# $(PYTHON), and $(PYTHON) is checked here.
# ---------------------------------------------------------------------------
.PHONY: py-version
py-version:
	@grep -qxF 'target-version = "py$(subst .,,$(PYTHON_VERSION))"' backend/pyproject.toml \
	  || { echo "backend/pyproject.toml: ruff target-version is not py$(subst .,,$(PYTHON_VERSION))"; exit 1; }
	@grep -qxF 'FROM python:$(PYTHON_VERSION)-slim' backend/Dockerfile \
	  || { echo "backend/Dockerfile: base image is not python:$(PYTHON_VERSION)-slim"; exit 1; }
	@$(PYTHON) -c "import sys; v = '.'.join(map(str, sys.version_info[:2])); \
	 sys.exit(0 if v == '$(PYTHON_VERSION)' else \
	 f'the gates are running on python {v}, not $(PYTHON_VERSION) - run: make back-install')"

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

back-test:
	cd backend && $(PYTHON) -m pytest

# The container is what the backend ships as, so this is what building the
# backend means. It used to be `python -c "import main"` — which four test
# modules already do on their way to an app fixture, so it proved nothing and
# was believed anyway, on the strength of its name. A pin that no longer
# resolves, a missing system package, a broken Dockerfile: all of them now fail
# here rather than on the television.
#
# Cheap because it is cached: about a second when nothing changed, two after a
# code change, and the full forty only when requirements.txt moves. Last in
# `backend` because it is the only one that needs a daemon, so everything that
# can fail cheaply has already had its turn.
#
# It does not touch the running board. Compose names an image after the
# directory it is run from, so a worktree builds `<worktree>-backend` and the
# board's own `stark-hud-backend` is left alone — the gate builds, it does not
# deploy, and the layers underneath are shared either way.
back-build:
	docker compose build backend

back-install:
	cd backend && python$(PYTHON_VERSION) -m venv .venv
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
.PHONY: agent-lint agent-types
agent-lint:
	cd backend && $(PYTHON) -m ruff check --config pyproject.toml ../tools
	cd backend && $(PYTHON) -m ruff format --check --config pyproject.toml ../tools
	cd backend && $(PYTHON) lint/house_lint.py ../tools

# The same argument as `back-types`, and more of it out here: ruff's ANN rules
# have demanded annotations in `tools/` from the day this target existed, and
# nothing ever read them — so the tree was annotated and unverified, which is
# the expensive kind of wrong.
#
# MYPYPATH is `../tools` because that is what these modules are to each other:
# `agent.py` is run as a script and finds `sources.py` beside it, with no
# package prefix. `pytest.ini` puts the same directory on its path for the same
# reason. Checking them as `tools.sources` would be checking an arrangement
# nobody runs.
agent-types:
	cd backend && MYPYPATH=../tools $(PYTHON) -m mypy --config-file pyproject.toml ../tools

# ---------------------------------------------------------------------------
# Frontend gates  (run from frontend/, driven by $(BUN))
# ---------------------------------------------------------------------------
.PHONY: front-lint front-quick front-dead front-build front-theme front-test front-install
front-lint:
	cd frontend && $(BUN) run check

# The same linters without `tsc`, which is over half of what front-lint costs.
front-quick:
	cd frontend && $(BUN) run lint

# Unused files, dependencies, imports that do not resolve — and unused exports
# and types, which this used to leave off because `lib/schemas/` mirrors the
# backend and `components/ui/` is a vendored primitive library, so knip found
# dozens of deliberate exports there and a gate that has to be argued with is
# one that gets switched off.
#
# Both are now named as entry points in `knip.json` instead, which says the same
# thing to the tool rather than to a reader, and the argument is gone: a public
# surface is a starting point, not a leftover. What is left has teeth — an
# exported function or constant nothing imports fails the build. Types are the
# one exemption, because a type naming an exported function's parameter is used
# by everyone who calls it and imported by nobody.
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
