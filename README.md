# stark-hud

A board on a television. Any Claude session writes to it over MCP and it
changes, live, in the room.

The screen has no keyboard and no mouse and nobody walks up to it. That single
fact decides most of what follows: nothing here is clickable, nothing scrolls
by hand, and anything you would normally reach for with a pointer is a tool
call instead.

## What it does

- **Renders a fixed grid**, 32×18 cells, that never scrolls. What does not fit
  becomes another page, and one page shows at a time.
- **Keeps itself on disk.** A `.hud` file, written atomically. Pull the plug and
  the board comes back — widgets, notifications, current page and all.
- **Pushes every change to every viewer** over a WebSocket. The television and a
  laptop see the same board at the same moment.
- **Takes an inbox of notifications** from any source, kept 48 hours, shown like
  a phone's shade.
- **Feeds itself** from a declarative list of shell commands (`tools/sources.toml`)
  that print JSON. CPU, memory, GPU, tmux sessions and your commits are all just
  that.
- **Plays media** — local audio and video, and YouTube — with a queue, from MCP,
  because there is no remote control in the room.
- **Says what it is doing.** A widget that cannot play a file or a video says so
  back to the server, where a session can read it.

## The widgets

| kind | what it is |
| --- | --- |
| `list` | A heading and entries: icon, title, description, each colourable. The general case — most of the others are it with fewer parts. |
| `text` | One line of prose, no card. |
| `note` | A sticky note on a tinted card. |
| `chart` | `line`, `bar`, `area`, `pie`, and `radial` gauges. Axes optional, colour thresholds optional. |
| `clock` | The time, with the date under it when there is room. |
| `inbox` | Where notifications are shown. |
| `feed` | Things that happened elsewhere, newest first, replaced whole on each refresh. |
| `media` | Audio, video or YouTube, with a queue, loop and maximise. |
| `image` · `video` | A local file, served by id — a path never reaches a URL. |
| `box` | A container other widgets can name as their parent. |

Every widget carries its own colour, text scale, background and opacity, plus a
`description` that only Claude reads — a note for whoever drives the board next.

## Architecture

```
                    ┌──────── stark-hud, one process ────────┐
                    │                                        │
   HTTP  /api  ─────┤  api/       handlers, one per route    │
   WS    /ws   ─────┤  services/  placement, pages, rules    │
   MCP   /mcp  ─────┤  repositories/  the board, and store.py│
                    │  schemas/   payloads, colour, icon, svg│
                    │                                        │
                    └──────┬──────────────────┬──────────────┘
                           │ board.hud        │ ws broadcast
                           ▼                  ▼
                      ┌─────────┐   ┌─────────┴──────────┐
                      │  disk   │   │  TV      · laptop  │
                      └─────────┘   └────────────────────┘
                           ▲
                           │ HTTP, every few seconds
                    ┌──────┴────────────────────────────────┐
                    │  tools/agent.py, on the host           │
                    │  runs tools/sources.toml → collectors  │
                    └────────────────────────────────────────┘
```

Four layers, and they stay in their lanes: `api/` translates HTTP, `services/`
decides, `repositories/` holds, `schemas/` defines what is legal. Placement is
settled on the server — a drag in a browser is a request, and the authoritative
answer comes back over the socket, so two viewers can never disagree.

The agent lives **outside** the containers on purpose. It reads `/proc`,
`nvidia-smi` and `tmux`, none of which describe the right machine from inside a
container.

## Running it

```bash
docker compose up -d --build      # board on :8080, MCP on :8000/mcp/
python tools/agent.py             # the feeder, on the host
```

Point a Claude session at it:

```json
{ "mcpServers": { "stark-hud": { "type": "http", "url": "http://<lan-ip>:8000/mcp/" } } }
```

`make check` is the only quality gate, and it is the whole of it — there is no
CI, so nothing catches a push whose gates were never run.

## If you are a Claude reading this

You will work the rest out from the code faster than from prose, so this is
directions rather than instructions.

- The MCP tool docstrings are the real manual. They are written for you and they
  say the things a session cannot guess.
- `CLAUDE.md` is the contract, and it wins over this file.
- Call `list_items` instead of remembering where anything is — a human may have
  dragged it, and a widget's `description` may be a note another session left you.
- Call `board_status` before adding anything large. A full board answers with a
  sentence saying what is free, not an exception.
- The board never fetches. If something should update on its own, it belongs in
  `tools/sources.toml`, not in a widget.
- Anything meant to survive belongs on the **item** (`description`, colour,
  position) rather than in its payload: a panel's payload is rewritten whole
  every few seconds.

## No authentication, deliberately

Anyone on the wifi can read and write the board. It shows the weather of one
machine on one television in one flat, and a token would buy nothing but the
feeling of a lock.

Which is why **commands live in `tools/sources.toml` on the host and never on
the board**. If the board carried commands, anything on the network could run
code here. A display should not be a remote shell.

For the decisions and their reasons, see [`SPEC.md`](./SPEC.md). For how to work
in this repository, [`CLAUDE.md`](./CLAUDE.md).
