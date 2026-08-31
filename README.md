# stark-hud

A blackboard shown on a TV. Any Claude session — or any browser on the LAN —
throws content at it and it renders, live.

Built on the [GoldStandard](https://github.com/) template with the database and
the login stripped out. See [`SPEC.md`](./SPEC.md) for the decisions and their
reasons, and [`CLAUDE.md`](./CLAUDE.md) for the operating contract.

## What it is

- **The TV is the only serious client.** It has no keyboard and no mouse and
  nobody touches it, so the board arranges itself and never scrolls.
- **State lives in memory.** Restart the server and the board is empty. Items
  are serializable Pydantic models behind a repository, so persisting to a file
  later means rewriting one module.
- **No authentication.** Anyone on the wifi can read and write the board.

## Architecture

```
              ┌─── stark-hud server (24/7) ───┐
              │  in-memory board state        │
              │  HTTP  ·  WebSocket  ·  MCP   │
              └───────────────────────────────┘
        ws ↙              ws ↓            ↘ MCP
      TV browser      other browsers    Claude sessions
```

Backend keeps the template's four layers: handlers in `api/`, contracts in
`schemas/`, state in `repositories/`, rules in `services/`. Placement is decided
server-side, so the frontend only translates grid cells into CSS grid — one
source of truth for layout, and no drag-and-drop library.

## Connecting a Claude session

The MCP server is mounted in the same process at `/mcp`, so it shares the board
directly — no second copy of the state and no HTTP hop between the tools and the
data. Point any machine on the LAN at it:

```json
{
  "mcpServers": {
    "stark-hud": {
      "type": "http",
      "url": "http://<the-pc-on-your-lan>:8000/mcp/"
    }
  }
}
```

Fourteen tools: `add_note`, `add_text`, `add_box`, `add_image`, `add_video`,
`add_chart`, `notify`, `move_item`, `resize_item`, `set_parent`, `remove_item`,
`clear_board`, `list_items`, `board_status`.

Placement failures come back as sentences, not exceptions — a full board answers
"no room, here is what is free" so the caller can pick a smaller size or clear
something. Call `board_status` before adding anything large.

Host checking is off deliberately: the board is open to the LAN, so validating
the `Host` header would only give a false sense of safety.

## Running it

```bash
make back-install && make front-install    # once
cd backend && .venv/bin/python -m uvicorn main:app --reload
cd frontend && bun run dev
```

The dev server proxies `/api` and `/ws` to the backend; nginx does the same in
production.

## Quality gates

`make check` runs everything CI runs — nothing more, nothing less.

```bash
make check                       # backend + frontend
make backend PYTHON=.venv/bin/python
make frontend
```
