"""The stand-in socket: one process that is the whole backend, as far as a board can tell.

A built bundle asks its own origin for three things and nothing else — the
board socket at `/ws`, the grid at `/api/v1/board/status`, and its own files.
So this serves all three on one port, and the board cannot tell it from nginx
in front of the real backend.

It is a stand-in and not the real backend on purpose. The real one is a
container, a database and the agent feeding it, which is three moving parts
between a measurement and its number; this is a fixed board and a clock. It
also means a sweep can run two of these at once, on two ports, serving two
builds, which is what interleaving needs.

`hold()` is the other half of the rig. Stop sending and the charts settle, and
a settled board is the only one whose picture can be compared to another's —
mid-animation, two identical builds differ.
"""

from __future__ import annotations

import functools
import http.server
import json
import threading
from pathlib import Path
from typing import Any

from perf import wire
from perf.board import CADENCE_S, Board

# The grid the board is drawn on. `use-grid.ts` refuses to draw anything at all
# until the server has said, so this is not optional furniture.
COLS = 32
ROWS = 18


class Feed:
    """A board's worth of data, and everyone currently being told about it."""

    def __init__(self, board: Board, cadence: float = CADENCE_S) -> None:
        self.board = board
        self.cadence = cadence
        self._clients: list[Any] = []
        self._lock = threading.Lock()
        self._held = threading.Event()
        self._stop = threading.Event()
        self.ticks = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "event": "board.snapshot",
            "data": {
                "items": self.board.items(),
                "showing": "main",
                # No background: a video is the other half of the board's cost and
                # it is not a thing a frontend branch changes. `live.py` prices it
                # on the television, where a decoder and a screen actually exist.
                "background": None,
                "ink": None,
                "notifications": [],
            },
        }

    def add(self, conn: Any) -> None:
        with self._lock:
            self._clients.append(conn)
        self.send(conn, self.snapshot())

    def drop(self, conn: Any) -> None:
        with self._lock:
            if conn in self._clients:
                self._clients.remove(conn)

    def send(self, conn: Any, message: dict[str, Any]) -> None:
        try:
            conn.sendall(wire.frame(json.dumps(message).encode(), mask=False))
        except OSError:
            self.drop(conn)

    def hold(self) -> None:
        """Stop the readings. The board settles, and its picture can be compared."""
        self._held.set()

    def resume(self) -> None:
        self._held.clear()

    def run(self) -> None:
        """Push a reading to every panel, every `cadence` seconds, until stopped."""
        while not self._stop.wait(self.cadence):
            if self._held.is_set():
                continue
            self.board.advance()
            self.ticks += 1
            for item in self.board.panels():
                message = {"event": "item.updated", "data": item}
                for conn in list(self._clients):
                    self.send(conn, message)

    def stop(self) -> None:
        self._stop.set()


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Static files, the grid, and the socket. Anything else is a deliberate 404."""

    feed: Feed

    def log_message(self, fmt: str, *args: Any) -> None:
        """Silence. A request log would be the noisiest thing on the box."""

    def do_GET(self) -> None:
        if self.path.split("?")[0] == "/ws":
            self._upgrade()
        elif self.path.startswith("/api/v1/board/status"):
            self._json(
                {
                    "showing": "main",
                    "pages": ["main"],
                    "cols": COLS,
                    "rows": ROWS,
                    "cells_total": COLS * ROWS,
                    "cells_used": 0,
                    "cells_free": COLS * ROWS,
                    "item_count": len(self.feed.board.items()),
                    "largest_free_rect": None,
                }
            )
        elif self.path.startswith("/api/"):
            # Media, speech and the rest. The fixture board asks for none of them,
            # and a 404 here is a louder failure than a stub that quietly works.
            self.send_error(404, "the rig serves the board socket and the grid, nothing else")
        else:
            super().do_GET()

    def _json(self, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _upgrade(self) -> None:
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(400, "not a websocket handshake")
            return
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", wire.accept_key(key))
        self.end_headers()
        self.wfile.flush()
        conn = self.connection
        self.feed.add(conn)
        try:
            # The board never sends anything up this socket, so this loop exists
            # only to notice the page going away — and to answer a ping, because
            # an unanswered one closes the connection and a reconnect in the
            # middle of a sample is a sample of a page loading.
            while True:
                message = wire.read_message(self.rfile)
                if message is None or message[0] == wire.CLOSE:
                    break
                if message[0] == wire.PING:
                    conn.sendall(wire.frame(message[1], wire.PONG, mask=False))
        except OSError:
            pass
        finally:
            self.feed.drop(conn)

    def translate_path(self, path: str) -> str:
        """Serve the built bundle, and fall back to its index like nginx does."""
        resolved = super().translate_path(path.split("?")[0])
        return resolved if Path(resolved).exists() else str(Path(self.directory) / "index.html")


class Server:
    """A built bundle, served with a live board behind it, on a port of its own."""

    def __init__(self, dist: Path, board: Board, port: int = 0, cadence: float = CADENCE_S) -> None:
        self.feed = Feed(board, cadence)
        bound = type("_Bound", (_Handler,), {"feed": self.feed})
        # `directory` is an __init__ keyword, not a class attribute: setting it on
        # the class is quietly overwritten per request and the server goes on
        # serving the working directory, which on this project is a git checkout.
        handler = functools.partial(bound, directory=str(dist))
        self._http = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        self._http.daemon_threads = True
        self.port = self._http.server_address[1]
        self._threads: list[threading.Thread] = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def start(self) -> None:
        for target in (self._http.serve_forever, self.feed.run):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self.feed.stop()
        self._http.shutdown()
        self._http.server_close()
