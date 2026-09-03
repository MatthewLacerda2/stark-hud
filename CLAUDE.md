# CLAUDE.md — the contract

This project is built on the **GoldStandard** template, which encodes
battle-tested patterns: a layered backend, an SDK-layered frontend, a token-based
design system, and a single `Makefile` that defines every quality gate. Build
new features by following the `board` domain through every layer.

The rules below are load-bearing. They are enforced by automated gates, not by
convention — keep them green.

## How we work

This section is about collaboration and judgment — how we talk about the work
and decide what's worth building. Like the working agreement below, **any of
these can be overridden by the user** (see the closing note).

- **Plain language over decoration.** Prefer plain language that explains what
  we — or the code — are doing, not highly technical decoration. The user is
  trying to architect intelligence, not ornament an implementation.
- **Solve the problem, not the solution.** It must always be clear to you the
  *problem* the user wants to solve, rather than the solution they're reaching
  for. A solution is just one way to create value for a problem; it is
  downstream of the problem. You and the user must share the fundamental truths
  of the problem — know its axioms — before building anything. It is your duty
  to hold the user to this too: if they are polishing a solution before the
  problem is pinned down, say so.
- **Align before building.** The user must have a clear, defined idea of what
  they are trying to say. If the idea isn't yet clear — to them or to you —
  stop: don't plan, don't implement. Get the idea defined for both of you
  first. Alignment of understanding comes before everything downstream.
- **Readable first, then tight.** First structure a good architecture and write
  code that is readable and organized. Then tighten it — denser, more compact —
  but compactness serves readability, it is not the finish line. If the clearest
  version of something isn't the densest, leave it clear. Don't end on clever
  one-liners nobody can debug later.
- **Push back when it's earned.**
  - If a feature or addition doesn't move the model's final performance, say so
    and say why it isn't pulling its weight.
  - If an idea contradicts what the literature has settled, flag it immediately.
    But calibrate: push hard on documented dead-ends, stay curious about
    genuinely untried ground. Research means trying what the literature hasn't
    settled — don't suppress a novel idea just because it's unproven. The line
    is "documented to fail" versus "simply not yet tried."
- **Looks beat handling.** A widget is what it shows. Chrome that exists only to
  make a widget easier to grab, label or configure — a title bar, a caption, a
  queue position, a name in a corner — comes off. A video widget draws video and
  nothing else; anything else appears on hover, where a pointer exists, and so
  never appears on the television at all.
  Dragging is a **second-class citizen** in this project. The user can ask a
  Claude to move, resize or restyle anything by name, so when handling and the
  look of the board disagree, the look wins. Do not add an affordance to the
  screen to make something easier to move.

- **Overriding these rules.** In the end, all rules may be overridden by the
  user — so long as the user says why, and the explanation still holds in the
  current context.

## What things are called

One word per thing, so a conversation and the code do not drift apart.

- **widget** — one block on the board. Not "node", not "tile", not "card". A
  node suggests a graph and a tile suggests decoration; this is a widget on a
  dashboard, and that is the ordinary word for it.
- **item** — the same thing on the wire. The API, the schemas and the MCP tools
  say `item` (`add_note`, `list_items`, `move_item`), and that stays: it is a
  published contract, and renaming it would buy nothing.
- **board** — everything on screen at once: the widgets, the background, the
  grid they sit on.
- **panel** — a widget that something writes to repeatedly, found by its `key`.
  Every panel is a widget; a one-off note is not a panel.
- **the agent** — `tools/agent.py`, the process on the host that feeds the
  panels. Not "the collector", which is one script it runs.

## Version control

This repository lives on GitHub as a **public** repo. Issues and pull
requests are in use.

- Commit freely and in small steps, so any change can be walked back.
- A commit message says *why*, not just what. `git log` is the record of intent.
- Small fixes go straight to `master`. Anything worth a second opinion goes on a
  branch and through a PR, because the user reviews the board by looking at it,
  not by reading a diff — see the worktree workflow below.

### Issues

An issue is the agreed *purpose and direction* of a piece of work, written
before it — an intention, not a spec. Because it is written before the work, its
suggestion may not survive contact with the code. When the work diverges, the
**pull request is the source of truth**: say so there, and reflect the gap back
into the issue if it still matters.

- **Title** starts with a scope tag — `[FE]` frontend, `[BE]` backend, `[FS]`
  fullstack, `[OT]` other (the agent in `tools/`, Docker, root files, docs). Tags
  are scan cues, not walls; work may cross one when the outcome needs it. Then a
  sentence that says the outcome, in this repo's plain voice — `[FE] A chart's
  title stops costing height`, not `[FE] Chart layout`.
- **Type label** (exactly one): `architecture` (structure and conventions —
  layer boundaries, the `backend/schemas/` ↔ `board.ts` contract, the `.hud` format),
  `infrastructure` (the machinery that constrains how we write — a `Makefile`
  gate, a lint rule, a test harness), `bug`, `documentation`, `foundation`
  (groundwork the board already assumes but does not have yet), `feature` (a new
  capability, built on top of all of that).
- **Stage label** (at most one, alongside the type): `planning` — we don't know
  how yet, or nobody has decided it's worth doing; both are the user's call — and
  `human`, which can't be finished by an agent alone.
- **`minor`** — ~30 lines or fewer, small enough to ride along in another
  issue's PR. A size marker, not a type: it stands alone or joins anything.
- **Assignment** — no assignee means free for grabs. When we start *actually
  working* an issue, assign the user and say so.

**Priority — `architecture` → `infrastructure` → `bug` → `foundation` →
`feature`; `documentation` never waits its turn.** This is "foundations come
first" written as an order: a missing boundary or contract and a missing gate
both halt everything downstream, then what is broken, then what the board
assumes and lacks, then what is new. Priority orders what gets **merged**, not
what gets **worked**.

**`planning` and `human` are absolute stops, and their absence means ready.** An
issue carrying neither is startable the moment it exists, including one filed a
minute ago. The judgement lives in the label, so an agent-written issue must
carry one if it is a breaking change, changes what the television shows, or needs
a call the user has not made. A `bug` usually should not — the deciding happened
when the board broke.

**The dependency graph is the plan.** Record how issues relate with GitHub's
**Blocked by / Blocks** and **sub-issues**; there are no rigid batches. Split by
responsibility, never by parallelism. Never split a payload change into a `[BE]`
and an `[FE]`: `frontend/src/lib/schemas/board.ts` mirrors `backend/schemas/` by
hand and no gate holds the halves together — that is one `[FS]` issue.

The same nine labels are used across the user's repos, so an issue reads the same
wherever it was filed. **Two skills carry the procedures** — `issue-write` and
`issue-batch` — so this file holds the reasoning and they hold the steps. Invoke
them rather than reconstructing one from memory, and name them when briefing a
subagent. Where a rule here is one line and a skill has ten, the line is the rule;
where they disagree, this file wins and the skill is wrong.

## Working agreement

These govern how the agent operates in this repo. **Any of them can be
overridden by the user in the current or a previous prompt** — an explicit
instruction wins.

- **Never commit or push** unless the user told you to in the current or a
  previous prompt.
- **Foundations come first.** The infrastructure, architecture, and gold-standard
  conventions/patterns must already be in place before any feature change is
  made. Don't build on top of a structure that isn't there yet — establish it.
- **Shared understanding before code.** Before implementing a change, the user
  must have a clear idea of what they want, and you must confirm you're on the
  same page. If the request is ambiguous, clarify first — don't guess and build.
- **Push back on dead weight.** If the user is trying to add something that
  doesn't add value to the project, you MUST push back. If you spot something
  that can be removed without losing value, you may suggest removing it.
- **Don't multiply Markdown.** Do not create new Markdown files without asking
  the user first. You may edit existing ones, as long as you tell the user what
  you changed.
- **Prefer expression over description.** An expressive, declarative structure
  (code, config, a linter rule that enforces a convention) is preferred over
  prose documenting that the convention exists. Make the codebase state the rule;
  don't just write about it.

## The no-drift meta-pattern

One `Makefile` defines every gate, and it is the only place a gate lives.
There is no CI: GitHub Actions was removed because it re-ran, on the user's
minutes, exactly what `make check` already runs before every merge. So a gate
that is not in the `Makefile` does not exist, and nothing catches a push that
skipped it.

```
make check      # everything
make backend    # back-lint + back-build + back-test
make frontend   # front-lint + front-build + front-test
```

**Gates must be green before you push.** Scope your run to the layer you touched
(`make backend` / `make frontend`) and run `make check` before opening a PR.

## Server-start guardrails

Do **not** auto-start dev servers, `docker compose up`, or long-running
processes to "check" something. Use the gates (build/test) to verify. If a human
needs a running app, ask them to start it.

## Language & i18n

- All code, comments, and docs are **English only**.
- User-facing frontend strings go through `i18next` (`src/i18n/`), never
  hardcoded in components.

## Worktree-per-session workflow

- New work: `git pull` the latest default branch → create a named git worktree
  off it → push a remote branch of the same name. Prefix `feat/` or `fix/`.
- Each worktree is DB-isolated: tests derive a per-worktree DB name so parallel
  sessions never collide.
- Name each session after what it's doing.

## Upgrade paths (intentionally deferred)

Each of these is deliberate, not forgotten. See `SPEC.md` for why. Persistence
and drag-and-resize used to be listed here and have both shipped — the board is
a `.hud` file on disk, and a widget can be dragged.

- **Auth:** none. The board is open to the LAN on purpose. A token would go in
  the API client and one dependency, not through the layers.
- **Typed SDK:** generate `lib/schemas/` from the backend OpenAPI spec instead
  of maintaining `board.ts` by hand alongside `board.py`.
