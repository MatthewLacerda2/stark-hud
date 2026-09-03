---
name: issue-write
description: Write an issue for this repo — what it must contain, which labels it carries, and when Claude may file one unprompted. Use when filing an issue, splitting an idea into issues, or deciding whether something noticed mid-work deserves one.
---

# Writing an issue

The unit of work here is a well-specified issue. A future Claude reads it **cold**
and says *"I understand the assignment, I know how to proceed."* That is what lets
an issue run unattended, overnight, with nobody to ask.

It is still an *intention*, not a contract. `CLAUDE.md` is explicit: the
*Suggestion* may not survive contact with the code, and when the work diverges the
**pull request** is the source of truth. Write the issue so someone can start
without you — not so nobody may deviate.

## What it contains

- **Context** — the problem, and what we want once it is addressed. This is the
  half that survives: a reason written down can be re-judged when circumstances
  change; one that was never written can only be obeyed or ignored.
- **Suggestion** — the shape of the work, *not* the implementation intrinsics.
  Name the decisions the implementer must make and leave them theirs. Mark the
  ones already settled **`(decided)`**; it is the cheapest way to tell "I chose
  this" apart from "someone must choose".
- **Definition of done** — the observable result, and the boundary. Say what is
  explicitly **out of scope**; a boundary stated once saves an argument later.
  Every issue's last line is the gate it must leave green: `make backend`,
  `make frontend`, or `make check`.

**Evidence beats assertion.** Quote the file, the lint rule, the failing test, the
line that is actually wrong. #40 opens with *"`repositories/board.py` says it
plainly: a key is unique 'by convention, not by constraint; the first match
wins'"* — nobody has to re-derive that. #31 names the four gate commands and says
which directory each one actually opens. "We should lint `tools/`" is worth less.

**Say what it looks like.** This is a board on a television, and most work here is
finally judged by looking at it. When a change is visible, describe what a person
across the room sees afterwards. When it is not visible at all, say that too.

**Cite what it relates to.** Sibling issues, the pull request that exposed it, the
rule in `CLAUDE.md` it turns on, the upgrade path in `SPEC.md` it finally takes. A
future reader arrives with no memory of today.

**Title carries a scope tag** — `[FE]`, `[BE]`, `[FS]`, `[OT]` (the agent in
`tools/`, Docker, root files, docs) — then a sentence that says the outcome in this
repo's plain voice. `[BE] A key names one widget, and nothing enforces it`, not
`[BE] Key uniqueness`.

## The three gates

An idea becomes an issue only when all three hold. If any fails, **push back
instead of complying**:

1. **Understanding** — restate the *problem*, not the solution the user reached
   for. `CLAUDE.md`'s "solve the problem, not the solution" is a gate, not a
   sentiment: a solution is downstream of a problem, and an issue written from the
   solution inherits whatever was wrong upstream of it. If unsure, restate and
   confirm; do not guess.
2. **Value** — real value to the board. No busywork, no features for their own
   sake. "Push back on dead weight" applies before the issue exists, not after.
3. **Craft** — this stack's good practice and this repo's own stated standards.
   They are not suggestions here; most of them are lint rules.

### What "Craft" means in this repo

An issue that cannot be implemented without breaking one of these is the wrong
shape — say so and propose the right one.

- **The backend layers, one direction.** `api/` → `schemas/` → `services/` →
  `repositories/`. **State is touched in `repositories/` and nowhere else** —
  there is no database, the board is a dict plus the `.hud` file, and the
  boundary is kept anyway so that changing how it persists stays a rewrite of one
  module.
- **Pydantic is the contract**, and `frontend/src/lib/schemas/board.ts` mirrors it
  **by hand**. Nothing checks that the two agree. Any issue that changes a request
  or response body is `[FS]` and owns both sides.
- **Payloads are a discriminated union on `kind`**, so an unknown kind is a 422
  that never reaches a handler. A new widget kind is a new member of that union,
  not a special case in a handler.
- **The board is finite.** The grid is fixed and never scrolls, so running out of
  room is a normal outcome, not an edge case. Nothing shrinks, evicts or overlaps
  silently: a request that does not fit gets a 409 saying what is free. An issue
  that would place a widget by making room is proposing to break that.
- **The frontend SDK layering.** Pages never `fetch`; they call
  `lib/api/<domain>.ts`, which calls `lib/api/client.ts` — the single place the
  base URL and error shape live. Streaming is the only exception.
- **The design system is an allowlist, not a guideline.** Semantic colour tokens
  and the typography scale only; raw palette classes, hex/`rgb()` literals and
  legacy `text-*` sizes all fail lint. UI composes shadcn primitives from
  `components/ui/`. One exported component per file.
- **All user-facing strings go through i18next.** Code, comments and docs are
  English only.
- **Looks beat handling.** A widget is what it shows. An issue whose outcome is a
  title bar, a caption, a name in a corner or any other chrome that exists to make
  a widget easier to grab or configure is the wrong shape: dragging is a
  second-class citizen, and anything of that sort belongs on hover, where a
  pointer exists and a television never is.
- **Length discipline is enforced, not encouraged.** Backend: file ≤ 350,
  endpoint handler ≤ 50, test ≤ 50 (`backend/tools/house_lint.py`). Frontend:
  `max-lines` 550. An issue whose honest shape is a 600-line module is an issue
  that needs splitting by responsibility first. Note that this ceiling fires on
  the *sum* of what merges, not on one branch — see `issue-batch`.
- **The no-drift rule.** Every gate is a `Makefile` target, and there is no CI to
  catch what skipped one. An issue that proposes a new check must put it in the
  `Makefile`; a check that lives only on a developer's machine does not exist.
- **Prefer expression over description.** If the outcome of an issue is "everyone
  remembers to do X", the issue is wrong — ask for the lint rule, the type, or the
  config that makes X the only reachable option.
- **Foundations come first.** An issue that builds on a structure that does not
  exist yet is two issues.

## Filing what you notice

Claude may open an issue autonomously, and should, for anything that will recur or
that a tool would solve more than once — provided the benefit outweighs the cost
of building it.

The strongest issues come from doing the work: a claim in `README.md` that quietly
became false, a gate that passes without looking at the file it was meant to check,
a panel that goes stale and looks fine doing it. Those are findings, and findings
are cheap to lose. A `bug` is always filable — the test above is about whether
something is worth *building*, never about whether a defect is worth *recording*.

**File rather than fix** when the thing found is outside the branch in hand. A
branch that grows to cover everything it noticed is a branch nobody can review.
When the user postpones something that must still happen, offer the issue then and
there.

**Do not transcribe a vague ask.** `CLAUDE.md` puts the bar before the issue, not
after it: the idea must be clear to both sides first. Surface the gaps, challenge
the assumptions, reach shared understanding — *then* write.

## Labels

This repo's scheme, from `CLAUDE.md`: **one type label, plus at most one stage
label.** The same set is used across all of the user's repos, so an issue reads the
same wherever it was filed.

**Type — one:**

- `architecture` — the project's structure and conventions: a layer boundary, the
  `backend/schemas/` ↔ `board.ts` contract, the `.hud` format, where a
  responsibility is allowed to live.
- `infrastructure` — the tools and guardrails around how we write: a `Makefile`
  gate, a lint rule, a test harness. #31 (`tools/` outside every gate) is the
  shape of this one.
- `bug` — something is broken.
- `documentation` — documentation.
- `foundation` — groundwork the board already assumes but does not have yet: a
  piece the rest of the project is written as though it had.
- `feature` — a new capability or resource, built on top of all of that.

The first three are one band in most schemes and three here, and the priority order
below is the reason. The question that separates them is **what the change is
about**: the shape of the product is `architecture`, the machinery that constrains
how it gets written is `infrastructure`, and something merely missing rather than
wrong is `foundation`.

**Stage — at most one, and its absence means ready:**

- `planning` — **never started.** It carries both "we do not yet know how" and
  "nobody has decided this is worth doing"; both are the user's call.
- `human` — cannot be finished by an agent alone. **Treat as not-ready.**

**`minor`** — ~30 lines or fewer, small enough that its resolution may ride along
in another issue's pull request. A size marker, not a type: it stands alone or
joins anything.

No amount of the issue looking startable overrides a stage label, and no amount of
it looking vague substitutes for one. **The judgement lives in the label**, so put
it on honestly: a Claude-written issue **must** carry one if it is a breaking
change, changes what the television shows, proposes a structural change, or needs a
call the user has not made.

A `bug` usually should **not** carry one — it is specific, the deciding already
happened when the board broke, and nothing is gained by making it wait.

## Priority

**`architecture` → `infrastructure` → `bug` → `foundation` → `feature`.**
`documentation` never waits its turn.

That is `CLAUDE.md`'s "foundations come first" expressed as an order: if the way we
build is not solid — a boundary or convention missing (`architecture`), a gate or
tool missing (`infrastructure`) — that halts everything downstream. Then what is
broken. Then what the board assumes and lacks. Then what is new.

Priority orders what gets **merged**, not what gets **worked**.

## Relationships

Use GitHub's **Blocked by / Blocks**, and **sub-issues** when one is literal
groundwork for another. Link when one lays groundwork, makes the next meaningfully
easier, or would conflict too much if done concurrently.

**The dependency graph is the plan** — there are no rigid batches.

**Do not split for parallelism.** Split by responsibility. Sub-issues that all land
in the same file are one issue; `issue-batch` names the files here that everything
collides in, and why splitting into them costs more than it saves. In particular,
**never split a payload change into a `[BE]` and an `[FE]`** — `board.ts` is
hand-mirrored and no gate holds the two halves together. That is one `[FS]` issue.

If a `planning` issue would change how another is implemented or thought of, mark
that other one **blocked by** it.

## Closing

The pull request that closes an issue is titled `{issue_number}-{branch_name}` and
its description opens with `Closes #{issue_number}` — and **check the number**. A
typo'd `Closes #N` closes the wrong issue or none, silently, and nothing verifies
it.
