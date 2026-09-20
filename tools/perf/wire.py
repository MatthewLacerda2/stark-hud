"""The WebSocket wire, in about a hundred lines of standard library.

Two things here speak this protocol and they face opposite ways: the stand-in
socket in `feed.py` is a *server* (it writes unmasked frames to the board), and
the driver in `cdp.py` is a *client* (it writes masked frames to Chromium). The
framing is the same either way, so it is written once.

There is a `websockets` package, and the backend's virtualenv has it. This does
not use it, on purpose: `tools/` is standard library only so that cron, a
systemd unit or a fresh clone can run what is in here with no environment at
all, and a measuring rig that first needs somebody to build a venv is a rig that
does not get run. What is actually needed is four opcodes and a mask, and that
is cheaper than the dependency.

No compression is negotiated. Chromium's DevTools endpoint offers
permessage-deflate only when asked, and a screenshot arriving as one large
uncompressed frame is less code than an inflate loop.
"""

from __future__ import annotations

import base64
import hashlib
import os
import struct
from typing import Protocol

# RFC 6455's magic string: the server appends it to the client's key, hashes,
# and hands back the digest, so that a cache cannot fake the handshake.
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

TEXT = 0x1
BINARY = 0x2
CLOSE = 0x8
PING = 0x9
PONG = 0xA


class Reader(Protocol):
    """Anything that reads exactly ``n`` bytes, or fewer only at end of stream."""

    def read(self, n: int, /) -> bytes: ...


def accept_key(key: str) -> str:
    """The `Sec-WebSocket-Accept` value for a client's `Sec-WebSocket-Key`."""
    return base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()


def frame(payload: bytes, opcode: int = TEXT, *, mask: bool) -> bytes:
    """One whole frame. `mask` is True writing to a server, False writing to a client."""
    head = bytearray([0x80 | opcode])
    size = len(payload)
    flag = 0x80 if mask else 0x00
    if size < 126:
        head.append(flag | size)
    elif size < 1 << 16:
        head.append(flag | 126)
        head += struct.pack("!H", size)
    else:
        head.append(flag | 127)
        head += struct.pack("!Q", size)
    if not mask:
        return bytes(head) + payload
    key = os.urandom(4)
    masked = bytes(b ^ key[i % 4] for i, b in enumerate(payload))
    return bytes(head) + key + masked


def _read_frame(reader: Reader) -> tuple[int, bool, bytes] | None:
    """Opcode, whether this frame ends the message, and its payload. None at EOF."""
    head = reader.read(2)
    if len(head) < 2:
        return None
    final = bool(head[0] & 0x80)
    opcode = head[0] & 0x0F
    masked = bool(head[1] & 0x80)
    size = head[1] & 0x7F
    if size == 126:
        size = struct.unpack("!H", reader.read(2))[0]
    elif size == 127:
        size = struct.unpack("!Q", reader.read(8))[0]
    key = reader.read(4) if masked else b""
    payload = reader.read(size)
    if masked:
        payload = bytes(b ^ key[i % 4] for i, b in enumerate(payload))
    return opcode, final, payload


def read_message(reader: Reader) -> tuple[int, bytes] | None:
    """One whole message, continuation frames joined. None at end of stream.

    A CDP screenshot of a 1920x1080 board is a couple of megabytes of base64,
    and Chromium is free to split that across frames. Joining them here is why
    the caller never has to know that.
    """
    opcode, final, payload = _read_frame(reader) or (None, None, None)
    if opcode is None or final is None or payload is None:
        return None
    body = bytearray(payload)
    while not final:
        nxt = _read_frame(reader)
        if nxt is None:
            return None
        _, final, more = nxt
        body += more
    return opcode, bytes(body)
