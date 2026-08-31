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
- **Overriding these rules.** In the end, all rules may be overridden by the
  user — so long as the user says why, and the explanation still holds in the
  current context.

## Version control

This repository is **local only**. There is no remote, no issues, and no pull
requests — that machinery from the template does not apply here yet.

- Commit freely and in small steps, so any change can be walked back.
- A commit message says *why*, not just what. `git log` is the only record of
  intent this project has.
- Work on `main` directly. Branch when an experiment might not survive.

If this ever gains a remote, the template's issue and PR rules can come back
wholesale — they were removed because they were unused, not because they were
wrong.

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

One `Makefile` defines every gate; **CI runs those exact targets.** Never add a
check that only runs in CI, or only locally.

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

Each of these is deliberate, not forgotten. See `SPEC.md` for why.

- **Persistence:** the board is a dict in `repositories/board.py`. Items are
  serializable models, so a `.hudtv` file is a rewrite of that module alone.
- **Auth:** none. The board is open to the LAN on purpose. A token would go in
  the API client and one dependency, not through the layers.
- **Drag and resize:** placement is decided server-side, so the frontend only
  renders cells. Adding `react-grid-layout` means writing layout changes back,
  and deciding who wins when the server and a browser disagree.
- **Typed SDK:** generate `lib/schemas/` from the backend OpenAPI spec instead
  of maintaining `board.ts` by hand alongside `board.py`.
