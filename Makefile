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
#   make perf     not a gate. Measures what the board costs, in a browser it
#                 starts itself or on the television. Minutes, not seconds, and
#                 it takes the same lock — see the note above `perf` below.
#
# Both say what the load average was, and the heavy ones take a lock on this
# machine so that two of them queue instead of fighting. A result is evidence
# only if you know what it was taken under.
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

# ---------------------------------------------------------------------------
# One heavy gate at a time, and every result says what it was taken under
#
# `make check` builds the frontend and runs both suites. Three at once take this
# 8-core machine past a load average of 14, and at that load a gate stops being
# evidence: on 2026-09-19 a test passed alone and failed inside `make check` at
# load 7, because one turn of the event loop was no longer enough for a resolved
# query to reach the DOM. The change was fine. The gate was not, and the only
# thing standing between that and a wrong conclusion was somebody remembering to
# read `uptime` first — a habit, not a gate.
#
# So a heavy target holds a lock on this *machine*, not on this checkout: the
# file is under /tmp on purpose, because every worktree shares the one CPU. A
# second arrival queues, and says so, because a gate that looks hung is a gate
# somebody kills.
#
# `gate` is deliberately outside the lock, and that was measured rather than
# assumed. It is linters only -- ruff, eslint, prettier and two greps -- and not
# one of them has a clock or a timeout, so none of them can go red because the
# machine is busy. A target that cannot lie under load gains nothing from
# waiting. It is also what `pre-commit` runs, and a commit that waits 45s on
# somebody else's test suite is a commit made with --no-verify. It still prints
# the load: the number costs nothing and the next reader may want it.
#
# The lock is held for a whole target rather than for each gate inside it, so
# these targets re-invoke make. A recipe's shell -- and so its lock -- lives for
# one logical line, and prerequisites all run before any recipe at all, so a
# prerequisite list cannot be held under one lock. STARK_GATE_LOCK marks a make
# that already holds it, so `check` calling `backend` does not queue behind
# itself.
# ---------------------------------------------------------------------------
LOCK  := /tmp/stark-hud-gate.lock
CORES := $(shell nproc)
LOAD   = $$(cut -d' ' -f1-3 /proc/loadavg)

# $(call heavy,<the targets this one actually is>)
define heavy
@if [ -n "$$STARK_GATE_LOCK" ]; then $(MAKE) --no-print-directory $(1); else \
	exec 9>$(LOCK); \
	flock -n 9 || { echo "gate: another gate has this machine - waiting for it"; flock 9; }; \
	echo "gate: starting at load $(LOAD) on $(CORES) cores"; \
	STARK_GATE_LOCK=1 $(MAKE) --no-print-directory $(1); status=$$?; \
	echo "gate: finished at load $(LOAD) on $(CORES) cores"; \
	exit $$status; \
fi
endef

.DEFAULT_GOAL := check

# ---------------------------------------------------------------------------
# Aggregate gates
# ---------------------------------------------------------------------------
.PHONY: check gate hooks backend agent frontend perf
check:
	$(call heavy,backend agent units-lint state frontend)

# Fast enough to run on every commit: what a linter can say without compiling,
# building or executing anything, plus `py-version`, which is two greps. The
# type check lives in `check` rather than here because it costs more than the
# rest of this target put together, and the container build lives there because
# it is the one gate that needs a docker daemon — pre-commit has to work on a
# machine where the daemon is not up.
gate:
	@echo "gate: linters only, at load $(LOAD) on $(CORES) cores"
	@$(MAKE) --no-print-directory py-version back-lint agent-lint units-lint front-quick

hooks:
	git config core.hooksPath .githooks
	@echo "hooks on: pre-commit runs 'make gate', pre-push runs 'make check'"

backend:
	$(call heavy,py-version back-lint back-types back-test back-build)

agent:
	$(call heavy,agent-lint agent-types)

frontend:
	$(call heavy,front-lint front-dead front-build front-theme front-test)

# ---------------------------------------------------------------------------
# What the board costs  (`tools/perf/`)
#
# Not a gate, and deliberately not reachable from `check`. It needs a browser,
# it wants a GPU to say anything about the card, and it takes minutes — and a
# gate that needs a graphics stack is a gate that cannot run on the machine
# where the code is written. `make check` stays runnable on a box with neither.
#
# It takes the lock anyway, and that is the one decision in this file worth
# arguing about. A gate under load goes red and somebody looks; a *measurement*
# under load comes back with a number, and a wrong number is believed. The 18x
# that `bun install` moved by between a quiet box and a busy one is the whole
# reason this target exists at all, so measuring while a sibling's `make check`
# builds the frontend would be the exact lie the rig was written to stop. It
# holds the machine for the length of the sweep and says so.
#
# The rig prints its own conditions on every run, including the load at both
# ends, because the lock stops a gate starting — it does not stop a training
# run, and this machine usually has one.
#
#   make perf                 what this working tree costs
#   make perf REF=master      this tree against master, interleaved
#   make perf LIVE=1          the television, four-way split, with a GPU figure
#
# LIVE attaches read-only to the kiosk's debugging port. It injects one
# stylesheet and pauses one video to take the split, and puts both back; it
# never navigates the page and never touches `state/`.
# ---------------------------------------------------------------------------
REF     ?=
LIVE    ?=
ROUNDS  ?= 4
SECONDS ?= 20
PERF_ARGS = --repo $(CURDIR) --rounds $(ROUNDS) --seconds $(SECONDS) \
            $(if $(REF),--ref $(REF)) $(if $(LIVE),--live)

perf:
	$(call heavy,perf-run)

.PHONY: perf-run
perf-run:
	cd tools && $(PYTHON) -m perf $(PERF_ARGS)

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
	cd backend && $(PYTHON) -m lint.house_lint .

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
#
# `tools/perf/` is under these two targets as well, and its own tests are in
# that same directory for the same reason. The rig itself needs a browser and
# is not a gate; the parts of it that decide whether a number is right — the
# websocket framing, the /proc field counting, the picture comparison — need
# neither, and each of them has a wrong version that returns a plausible
# number rather than an error.
# ---------------------------------------------------------------------------
.PHONY: agent-lint agent-types
agent-lint:
	cd backend && $(PYTHON) -m ruff check --config pyproject.toml ../tools
	cd backend && $(PYTHON) -m ruff format --check --config pyproject.toml ../tools
	cd backend && $(PYTHON) -m lint.house_lint ../tools

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
# state/, when this machine has one
#
# `state/` is the instance: the sources file, the board file, and the scripts a
# source runs. It is gitignored, it is a git repository of its own with no
# remote, and keeping it out of this one was the right call — a change of focus
# should not need a pull request. The price was that it sat outside every gate,
# and what is in it is not scratch work: `trm_watch.py` is what puts four sheets
# and a progress bar on the television, and when it breaks the board goes stale
# while still looking fine, which is the failure this project is worst at
# noticing.
#
# So the gate reaches in when there is something to reach into, and says nothing
# at all when there is not: a fresh clone has no `state/` and passes without a
# word. This repository knows `state/` may exist. It does not know what is in
# it — whatever Python is there is linted and type-checked, and whatever tests
# are there are run.
#
# Two of this project's own gates are deliberately not pointed at it.
# `ruff format --check` is house style, and `state/` is not this house.
# `lint/house_lint.py` is more so: every rule in it is about this backend's
# layers and this repository's ceilings, and the instance never agreed to them.
# What is left — ruff's lint rules, mypy, and the tests — is the half that
# catches a break rather than a preference.
#
# Found from a worktree as well as from the checkout, because there is one
# `state/` on this machine and the worktrees are where the work happens. A gate
# that only fires in the main checkout is a gate nobody runs, which is the same
# as not having one.
# ---------------------------------------------------------------------------
STATE := $(firstword $(wildcard $(CURDIR)/state $(MAIN)/state))

.PHONY: state
ifeq ($(STATE),)
state:
	@echo "state: nothing here to gate (no state/ - this clone feeds no board yet)"
else
state:
	@echo "state: gating $(STATE)"
	cd backend && $(PYTHON) -m ruff check --config pyproject.toml $(STATE)
	cd backend && MYPYPATH=../tools:../tools/mesh $(PYTHON) -m mypy --config-file pyproject.toml $(STATE)
# pytest's own config, because `state/` has none and is not getting one; its
# exit code 5 is "no tests here", which is a fresh instance and not a failure.
# Nothing of pytest's is left behind in a directory this repository does not own.
	cd backend && $(PYTHON) -m pytest -c pytest.ini -p no:cacheprovider $(STATE) || [ $$? = 5 ]
endif

# ---------------------------------------------------------------------------
# What runs this board on a machine  (`units/`)
#
# The containers need no unit: `restart: unless-stopped` plus a docker daemon
# enabled at boot is the whole of their autostart story. Two things are left,
# and until now they lived only in one person's home directory, where nothing
# reviewed them, nothing gated them, and a clone could not reproduce them —
# which is how the agent's unit came to say the board was in memory two months
# after the board became a file.
#
#   units/stark-hud-agent.service   the agent, as a systemd user service
#   units/stark-hud.desktop         the kiosk, as an XDG autostart entry
#
# The kiosk is not a unit because it cannot be one: it needs the graphical
# session, and an autostart entry is what starts after that session exists
# rather than beside it. `tv-remote.service` is not here either, and that is a
# decision rather than an oversight — it is the owner's own tool, it lives in
# ~/.local/share/tv-video/, and it is not this board.
#
# Both are symlinked rather than copied, so the repository stays the copy of
# record and an edit here is an edit there. The one thing the agent needs that
# this repository must not hold — where the checkout is — is written into a
# drop-in instead, beside the `orgs.conf` somebody wrote by hand for the same
# reason. This file is public; a home directory and a LAN address are not.
#
# `$(MAIN)` and not `$(CURDIR)`: run from a worktree, this still points systemd
# at the checkout the board runs from, rather than at a branch that will be
# deleted next week.
#
# Point UNITS_DIR and AUTOSTART_DIR at a scratch directory and this installs
# there and leaves systemd alone, which is how it is tested without touching a
# running board.
# ---------------------------------------------------------------------------
UNITS_DIR     ?= $(HOME)/.config/systemd/user
AUTOSTART_DIR ?= $(HOME)/.config/autostart
DROP_IN        = $(UNITS_DIR)/stark-hud-agent.service.d

.PHONY: units units-lint
units:
	@mkdir -p $(UNITS_DIR) $(DROP_IN) $(AUTOSTART_DIR)
	ln -sfn $(MAIN)/units/stark-hud-agent.service $(UNITS_DIR)/stark-hud-agent.service
	ln -sfn $(MAIN)/units/stark-hud.desktop $(AUTOSTART_DIR)/stark-hud.desktop
	@printf '%s\n' \
	  '# Written by `make units`, and not in the repository: where this checkout' \
	  '# is, which belongs to this machine and to nobody else.' \
	  '[Service]' \
	  'WorkingDirectory=$(MAIN)' > $(DROP_IN)/10-checkout.conf
	@if [ "$(UNITS_DIR)" = "$(HOME)/.config/systemd/user" ]; then \
		systemctl --user daemon-reload; \
		systemctl --user enable stark-hud-agent.service; \
		echo "units: installed and enabled. The running agent is still the old one:"; \
		echo "       systemctl --user restart stark-hud-agent   when the board can blink."; \
	else \
		echo "units: installed into $(UNITS_DIR) and $(AUTOSTART_DIR), systemd left alone."; \
	fi

# Both files are read by something that is not here when it is wrong: systemd at
# boot, and the session manager at login. The kiosk's Exec line already went in
# wrong once and was caught by this rather than by a television showing nothing.
#
# Each check is skipped when its tool is missing, because neither is worth a
# dependency on a machine that only ever builds this repository — and both ship
# with the desktop that runs the board.
units-lint:
	@if command -v systemd-analyze >/dev/null; then \
		systemd-analyze --user verify units/stark-hud-agent.service; \
	else echo "units-lint: no systemd-analyze here - unit not verified"; fi
	@if command -v desktop-file-validate >/dev/null; then \
		desktop-file-validate units/stark-hud.desktop; \
	else echo "units-lint: no desktop-file-validate here - entry not verified"; fi

# ---------------------------------------------------------------------------
# Frontend gates  (run from frontend/, driven by $(BUN))
# ---------------------------------------------------------------------------
.PHONY: front-lint front-quick front-dead front-build front-theme front-test front-install
front-lint: front-install
	cd frontend && $(BUN) run check

# The same linters without `tsc`, which is over half of what front-lint costs.
front-quick: front-install
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
front-dead: front-install
	cd frontend && $(BUN) run dead

front-build: front-install
	cd frontend && $(BUN) run build

# Reads the built stylesheet, not the source. Tailwind emits only the theme
# variables it sees a class using, and the board takes colour names over the
# wire — so a name the backend accepts can be one the build dropped, which the
# browser resolves to nothing and paints black. Runs after front-build for the
# obvious reason: there is no artefact to read before it.
front-theme: front-install
	cd frontend && $(BUN) run check-theme

front-test: front-install
	cd frontend && $(BUN) run test

# ---------------------------------------------------------------------------
# node_modules, and why a worktree does not get its own
#
# A fresh worktree has none, so every frontend gate in one used to begin with a
# 430-package install: 14.4s and 356 MB, measured here on 2026-09-20, for a tree
# byte-identical to the one the main checkout already has. Five worktrees is
# 1.8 GB -- of RAM, because a worktree lives on tmpfs -- on the machine whose
# load is the thing that makes gates lie.
#
# Both obvious answers were measured, and both are wrong. `--backend=hardlink`
# is already bun's default and buys nothing: in the main checkout every
# installed file is *already* a hardlink into bun's cache (nlink >= 2), and in a
# worktree not one of them can be (nlink = 1, all 24,622 of them), because /tmp
# is tmpfs, the cache is on ext4, and a hardlink does not cross a filesystem.
# `--backend=symlink` does cross it, in 0.4s and 568 KB -- and then `bun run
# check` fails with a dozen invented type errors, because every file is a
# symlink into the cache, tsc resolves the realpath, and a package sitting in
# the cache cannot see its peers.
#
# What survives is the whole tree, borrowed: 19 ms, nothing on disk, gates green.
# It is correct only while the two trees are the same tree, so it is taken only
# while this worktree's bun.lock and package.json are byte-identical to the main
# checkout's -- checked on every run, so a branch that changes a dependency
# quietly stops borrowing and installs its own. The main checkout has nobody to
# borrow from and always installs; a fresh clone is that case, and
# `make front-install` is still the one command it needs.
#
# Nothing is ever installed *through* the borrowed link: the symlink is removed
# before `bun install` runs, so a worktree cannot write into another checkout.
# ---------------------------------------------------------------------------
front-install:
	@cd frontend && \
	if [ "$(MAIN)" != "$(CURDIR)" ] && [ -d "$(MAIN)/frontend/node_modules" ] \
	   && cmp -s bun.lock "$(MAIN)/frontend/bun.lock" \
	   && cmp -s package.json "$(MAIN)/frontend/package.json"; then \
		if [ ! -L node_modules ]; then \
			rm -rf node_modules; \
			ln -s "$(MAIN)/frontend/node_modules" node_modules; \
			echo "front-install: borrowing the main checkout's node_modules (lockfile matches)"; \
		fi; \
	else \
		if [ -L node_modules ]; then rm -f node_modules; fi; \
		$(BUN) install; \
	fi
