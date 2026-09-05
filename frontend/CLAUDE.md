# Frontend — local contract

React 19 + TanStack Router/Query + Tailwind, with a token-based design system
enforced by ESLint. The root `CLAUDE.md` is the source of truth; this file is
the frontend-local view. Gates live in the root `Makefile` (`make frontend`)
and are enforced by the git hooks in `.githooks`, not by CI — there is none.

## Data flow (pages never fetch)

`routes/` → `lib/api/<domain>.ts` → `lib/api/client.ts`. `client.ts` is the
single place the API base URL and error shape live (there is no auth; streaming is the
only allowed exception). `lib/schemas/` mirrors the backend Pydantic models.

## Design system (all ESLint errors — see `eslint.config.ts`)

- **Compose shadcn primitives** from `components/ui/`. Never hand-roll a text
  `<input>`/`<select>`/`<textarea>`; add primitives with
  `bunx shadcn@latest add <name>`.
- **Typography tokens only** (`text-display`, `text-h1`…`text-caption`,
  `text-kpi-*`). No legacy `text-xs…3xl`, no arbitrary `text-[Npx]`. Tokens
  carry weight/line-height — don't repeat `font-*` next to them.
- **Color is an allowlist** of semantic tokens. No raw palette classes
  (`bg-red-500`), no hex/`rgb()` literals in `className`/`style`.
- **Motion is a token set too**, in `styles.css` beside the colours:
  `--motion-settle` for a widget going somewhere else, `--motion-arrive` and
  `--motion-leave` for one appearing or going. Nothing invents an easing at
  runtime — the set grows by a commit, or the board stops looking like one
  thing. Motion moves and scales; it never recolours.
- **One exported React component per file** (`components/ui/**`, barrels, and
  Router objects exempt).
- ≤ 550 lines per `.ts`/`.tsx` (`mock-*.ts` exempt).

## i18n

User-facing strings go through `i18next` (`src/i18n/`), never hardcoded in
components.

## Gate before pushing

`make frontend` = `front-lint` (`bun run check`: tsc + eslint + prettier) ·
`front-build` (vite) · `front-test` (vitest). Green before you push.
