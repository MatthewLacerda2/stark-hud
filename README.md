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

Day to day, as two containers that come back on their own:

```bash
docker compose up -d --build     # start, and rebuild after a code change
docker compose logs -f
docker compose down              # stop
```

The board is then at `http://<this-machine>:8080`, and the MCP server at
`:8000/mcp/` or `:8080/mcp/` — nginx proxies both `/api` and `/mcp`, so one port
is enough if you prefer it.

`restart: unless-stopped` plus a docker daemon enabled at boot is the whole of
the autostart story. `~/.config/autostart/stark-hud.desktop` opens the browser
full-screen on the TV at login, fifteen seconds later so the containers are
answering by the time the page loads.

For development, with hot reload:

```bash
make back-install && make front-install    # once
cd backend && .venv/bin/python -m uvicorn main:app --reload
cd frontend && bun run dev                 # already listens on 0.0.0.0
```

Either way the frontend proxies `/api` and `/ws` to the backend — Vite in
development, nginx in the containers.

## Notifications

They are not tiles. Everything announced goes into one inbox, shown by an
`inbox` item the way a phone's shade shows its own — icon, source, time, title,
body — newest first. How many are visible is how tall that tile is, and how
much of each line fits is how wide.

They are kept for 48 hours and drop out on their own. Like the board itself,
they are written to disk and survive a restart.

```bash
curl -X POST localhost:8000/api/v1/notifications -H 'Content-Type: application/json' \
  -d '{"title":"deploy done","body":"12 tests","icon":"rocket","source":"ci"}'
```

`icon` is a name from a closed set — bell, check, info, alert-triangle,
alert-circle, x-circle, terminal, git-branch, download, upload, cpu, hard-drive,
mail, message-square, clock, zap, flame, bug, rocket, wrench — or an absolute
path to an image. Anything else is refused with the list, because a typo would
otherwise draw nothing and never say why.

## Feeding it

The board never fetches — it draws what it is given — so something has to push.
`tools/agent.py` does, driven by `tools/sources.toml`. A source says three
things and nothing else:

```toml
[[source]]
name = "cpu"                                    # stable key: refreshes in place
command = "python3 {collectors}/cpu.py"         # where (or: url = "...")
every = 3                                       # how often, in seconds
place = { x = 0, y = 0, w = 12, h = 7 }         # optional; omit to auto-place
panel = { kind = "chart", chart = "bar", title = "CPU por núcleo",
          x_key = "core", series = ["use"], max = 100 }
```

The contract is just: **print JSON on stdout** — the rows of the chart, or plain
text for a note. Any language, any tool. `history = N` keeps the last N rows, so
a source that prints one reading becomes a line without remembering anything
itself; that is how the temperature chart works.

```bash
python tools/agent.py           # run it
python tools/agent.py --once    # one pass, for testing
```

**Commands live in that file and never on the board.** The board is open to the
whole LAN, and if it carried commands, anything on the wifi could run code on
this machine. A display should not be a remote shell.

It remembers which item is which panel in `~/.local/state/stark-hud-panels.json`,
so a refresh rewrites contents and leaves position alone — which is what lets you
drag a tile and keep it there. It runs on the host, not in a container: `/proc`,
`nvidia-smi` and `tmux` describe a machine, and inside a container they would
describe the wrong one.

## Quality gates

`make check` runs everything CI runs — nothing more, nothing less.

```bash
make check                       # backend + frontend
make backend PYTHON=.venv/bin/python
make frontend
```
