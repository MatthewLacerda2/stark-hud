"""In-process WebSocket fan-out.

Every mutation broadcasts the event to all connected clients. There is one
process and one board, so a plain list of sockets is the whole design; a dead
socket is dropped on the first failed send rather than tracked separately.
"""

import asyncio
from typing import Any

from fastapi import WebSocket


class Hub:
    """Tracks connected clients and pushes board events to them."""

    def __init__(self) -> None:
        self._clients: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, socket: WebSocket) -> None:
        """Accept a socket and remember it."""
        await socket.accept()
        async with self._lock:
            self._clients.append(socket)

    async def disconnect(self, socket: WebSocket) -> None:
        """Forget a socket; safe to call for one already gone."""
        async with self._lock:
            if socket in self._clients:
                self._clients.remove(socket)

    async def broadcast(self, event: str, data: Any) -> None:
        """Send one event to every client, dropping the ones that fail."""
        message = {"event": event, "data": data}
        async with self._lock:
            targets = list(self._clients)
        dead: list[WebSocket] = []
        for socket in targets:
            try:
                await socket.send_json(message)
            except Exception:  # noqa: BLE001 - a broken client must not break the rest
                dead.append(socket)
        for socket in dead:
            await self.disconnect(socket)

    @property
    def client_count(self) -> int:
        """How many clients are currently connected."""
        return len(self._clients)


hub = Hub()
