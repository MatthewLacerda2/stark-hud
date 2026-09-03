---
name: issue-batch
description: Run several pieces of work at once in this repo — how many agents to have going, which ones collide, when a green gate is lying, and what deploying costs. Use when starting more than one branch, when spawning subagents, or when the user is dictating new work faster than one branch can absorb it.
---

# Working several things at once

The user does not hand over one task. He watches the board, has an idea, and
describes the next one while the last is still being built. A session here is a
queue that keeps growing, and most of it can genuinely run in parallel.

This is what that costs, and where it goes wrong. Every rule below was paid for.

## The bottleneck is the machine, not the merge queue

Nothing here is compiled: `make check` is quick and a rebase is a small `git
merge`. Four branches in flight cost almost nothing to reconcile — the
arithmetic that makes Rust projects serialise their merges does not apply.

**What does apply is CPU.** Several agents running `bun install` and vite builds
at once will bury this machine, and a buried machine makes `make check` **lie**:
tests that pass on their own time out while competing for a core, and go red
over nothing that is in the diff. Two separate agents hit this independently and
both diagnosed it correctly before believing it.

Run the gate yourself before you believe a number anybody writes down about it,
this file included. What it costs depends on the machine, what else is on it,
and what has changed since — which is why none of that is written here.

So:

- **At most two agents building the frontend at the same time.** A third is not
  faster; it makes all three untrustworthy.
- **A red gate under load is re-run, not believed.** Check `uptime` first. Once
  load is up around the core count, the result means nothing either way.
- A green gate under load is not proof either — but nobody is tempted by that
  one.

## The files where everything collides

Two agents in different areas almost never conflict here. Two agents in any of
these will:

| file | why |
| --- | --- |
| `backend/schemas/payloads.py` | every widget kind is appended here |
| `backend/hud_mcp/server.py` | every tool registers here |
| `frontend/src/hooks/use-board.ts` | every socket event lands in one reducer |
| `frontend/src/routes/index.tsx` | one destructure feeds the whole page |
| `frontend/src/components/board/board-grid.tsx` | every per-widget style passes through |
| `frontend/src/components/board/items/chart.tsx` | every chart feature |

Both real conflicts in a day of parallel work were two agents adding a field to
the same line of `use-board.ts` and `index.tsx`. Trivial to resolve — but only
if you know to look.

**Name the siblings and their files in every brief.** An agent told which files
belong to somebody else keeps its diff out of them.

## The house lint fires on the sum

`backend/schemas/*.py` has a 350-line ceiling. It was broken **three times in one
day**, and not once by a single branch: each pull request passed alone and the
combination went over.

**So the gate that matters is run on the merge, not on the branch.** Merge
everything locally, run `make check`, and only then push. Each time this fired
there was a real seam underneath — colour, icon, svg, media, payloads all became
their own modules because of it — so treat it as an alarm rather than an
obstacle, and split along meaning rather than trimming comments to fit.

## Deploying interrupts a room

This is the constraint no other project has. `docker compose up --build` reloads
the page on a television in someone's home, and whatever was playing stops.

- **Before rebuilding, look at what is playing.** A media widget now keeps its
  position, so a film resumes — but check, and say what you did.
- **Do not deploy for one commit at a time.** Batch the merges, deploy once.
- **Never let a subagent build or deploy.** Say so in the brief, every time. A
  preview stack of its own is fine and sometimes necessary — its own `-p` project
  name and its own port, never the production containers, never `state/board.hud`,
  never the browser on debugging port 9222.

## Make the agent measure

The single largest difference between a good result and a plausible one.

Every wrong conclusion in a long session came from reasoning about code that was
not read, or from a symptom explained without evidence: a compactor blamed for
moves a browser made, a "stale build" that was real but found only by reading the
DOM, a path called broken because one file was read and not the compose file
beside it.

Everything that came out right had a number attached: pixels counted at eleven
viewport heights, `nvidia-smi` decoder utilisation at 0%, CPU measured with the
background paused and playing, a PipeWire sink moving out of `SUSPENDED`.

**So brief for evidence.** Tell an agent what to measure and with what. Give it
what it needs to see — a preview stack, a screenshot route, a way to read the
live state. "It works now" from an agent that could not observe anything is worth
nothing.

Two measuring traps this repo already found:

- `chromium --headless --window-size=1920,1080` lays the page out at **1920x993**
  and writes a 1920x1080 file. Every edge measured that way is wrong. Use CDP
  `Emulation.setDeviceMetricsOverride`.
- `top`'s first sample is an average since boot. Read the second one.

## Never filter a gate's output

`make check 2>&1 | grep -E "passed"` will show you ruff saying `All checks
passed!` while pytest is failing underneath. This has already put a red test on
`master`.

The same applies to a merge: `git merge | tail -3` showed one conflict when there
were four, and the other three were committed with their markers still in.

**Read the end of the output, not a slice of the middle.**

## Briefing a subagent

Give it, in this order:

1. **Its own worktree**, created for it, with the exact command. Never two
   branches taking turns in one checkout.
2. **`CLAUDE.md` first**, then the specific files it will touch.
3. **What has landed recently** that it must build on, by name — `master` moves
   under long-running agents, and one that rebased itself found this out the
   polite way.
4. **The siblings and their files.**
5. **No docker builds, no deploy.** Say it plainly.
6. **What to measure**, and what it is allowed to use to measure it.
7. **What is out of scope**, stated once.

Tell it to open a pull request and **not merge** — merging is the batch's job,
because only the batch knows what else is in flight.

Anything that spends money or quota (the ElevenLabs account is on a free tier)
is **forbidden to the agent** and done once by the session, deliberately.

## Reporting back

The user is not reading the transcript. It is notes for Claude.

**Say what the result was, and say what surprised you.** A surprise is not a
failure — a hypothesis dying to a measurement is the process working, and it is
the part worth writing down, because next time it is knowledge instead of a
guess.

Two things interrupt regardless: **a change to the user's own files outside the
repo**, and **a decision reversed** — where the instruction said one thing and
the branch did another. Both are only overrulable while the work is still
running.
