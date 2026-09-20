"""Driving a browser over the DevTools protocol, and the flag that must not be used.

Two shapes of browser are driven from here. `launch()` starts one of our own —
its own profile directory, its own debugging port, nothing shared with anything
on this machine — which is what a before/after sweep needs, because it needs
two at once. `attach()` connects to one that is already running, which is how
the television is measured: read-only, on the port the kiosk already opens.

**`--window-size=1920,1080` is not used here and must not be.** Headless
Chromium takes it as the *window*, subtracts its own chrome, and lays the page
out at 1920x993 while still writing a 1920x1080 image. Every edge measured that
way is in the wrong place and the screenshot looks right, which is the worst
combination available. `Emulation.setDeviceMetricsOverride` sets the viewport
itself and is what `viewport()` below calls.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from perf import wire

STARTUP_TIMEOUT_S = 20.0
CALL_TIMEOUT_S = 60.0


class CdpError(RuntimeError):
    """The browser answered, and the answer was an error."""


@dataclass(frozen=True)
class Process:
    """One process of a browser instance, as the browser itself names it."""

    pid: int
    type: str


class Connection:
    """One DevTools websocket, used one blocking call at a time.

    Events that arrive between a request and its reply are dropped on the
    floor. The rig asks questions; it does not watch for things happening.
    """

    def __init__(self, ws_url: str) -> None:
        host, port, path = _split(ws_url)
        self._sock = socket.create_connection((host, port), timeout=CALL_TIMEOUT_S)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self._sock.sendall(request.encode())
        self._file = self._sock.makefile("rb")
        while True:
            line = self._file.readline()
            if line in (b"\r\n", b"\n", b""):
                break
        self._next_id = 0

    def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call one method and return its result, raising on the protocol's own errors."""
        self._next_id += 1
        call_id = self._next_id
        body = json.dumps({"id": call_id, "method": method, "params": params or {}})
        self._sock.sendall(wire.frame(body.encode(), mask=True))
        while True:
            message = wire.read_message(self._file)
            if message is None:
                raise CdpError(f"the browser went away during {method}")
            opcode, payload = message
            if opcode == wire.PING:
                self._sock.sendall(wire.frame(payload, wire.PONG, mask=True))
                continue
            if opcode != wire.TEXT:
                continue
            reply = json.loads(payload)
            if reply.get("id") != call_id:
                continue
            if "error" in reply:
                raise CdpError(f"{method}: {reply['error']}")
            result: dict[str, Any] = reply.get("result", {})
            return result

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


def _split(ws_url: str) -> tuple[str, int, str]:
    rest = ws_url.removeprefix("ws://")
    authority, _, path = rest.partition("/")
    host, _, port = authority.partition(":")
    return host, int(port or 80), "/" + path


class Page:
    """A tab, and the three things the rig ever asks one to do."""

    def __init__(self, ws_url: str) -> None:
        self.cdp = Connection(ws_url)
        self.cdp.send("Runtime.enable")
        self.cdp.send("Page.enable")

    def viewport(self, width: int, height: int) -> None:
        """Lay the page out at exactly this size. See the note at the top of this file."""
        self.cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
        )

    def navigate(self, url: str) -> None:
        self.cdp.send("Page.navigate", {"url": url})

    def evaluate(self, expression: str) -> Any:
        """Run an expression in the page and bring back its value.

        `awaitPromise` because half of what the rig asks takes a frame or two —
        a settle, a screenshot of a chart that has stopped moving.
        """
        result = self.cdp.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if "exceptionDetails" in result:
            raise CdpError(f"in the page: {result['exceptionDetails'].get('text')}")
        return result.get("result", {}).get("value")

    def screenshot(self) -> bytes:
        data = self.cdp.send("Page.captureScreenshot", {"format": "png"})
        return base64.b64decode(data["data"])

    def close(self) -> None:
        self.cdp.close()


class Browser:
    """A whole browser instance: its processes, and the page the board is on."""

    def __init__(
        self, port: int, process: subprocess.Popen[bytes] | None, profile: Path | None
    ) -> None:
        self.port = port
        self._process = process
        self._profile = profile
        self.cdp = Connection(_version(port)["webSocketDebuggerUrl"])

    @classmethod
    def launch(cls, url: str, port: int, profile: Path, *, headless: bool = True) -> Browser:
        """Start a browser of our own, sharing nothing with any that is running."""
        profile.mkdir(parents=True, exist_ok=True)
        argv = [
            _chromium(),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            # The board's video would otherwise wait for a click that will never
            # come, and a background that never starts is a cost never measured.
            "--autoplay-policy=no-user-gesture-required",
            "--hide-scrollbars",
        ]
        if headless:
            argv.append("--headless=new")
        argv.append(url)
        process = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _wait_for(port)
        return cls(port, process, profile)

    @classmethod
    def attach(cls, port: int) -> Browser:
        """Connect to a browser somebody else started — the kiosk, in practice."""
        _version(port)
        return cls(port, None, None)

    def page(self, page_id: str | None = None) -> Page:
        """The board's tab: the one named, or the first page there is."""
        targets = json.loads(_get(f"http://127.0.0.1:{self.port}/json/list"))
        pages = [t for t in targets if t.get("type") == "page"]
        if page_id:
            pages = [t for t in pages if t.get("id") == page_id]
        if not pages:
            raise CdpError(f"no page target on port {self.port}")
        return Page(pages[0]["webSocketDebuggerUrl"])

    def processes(self) -> list[Process]:
        """Every process of this instance, as the browser names them.

        Asked of the browser rather than worked out by matching command lines:
        a renderer is a `--type=renderer` among hundreds on a busy box, and the
        browser is the only thing that knows which ones are its own.
        """
        info = self.cdp.send("SystemInfo.getProcessInfo")
        return [Process(int(p["id"]), str(p["type"])) for p in info.get("processInfo", [])]

    def close(self) -> None:
        self.cdp.close()
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()


def _chromium() -> str:
    for name in ("chromium", "chromium-browser", "google-chrome-stable", "google-chrome"):
        found = subprocess.run(["which", name], capture_output=True, text=True, check=False)
        if found.returncode == 0:
            return found.stdout.strip()
    raise CdpError("no chromium on PATH - the rig needs a browser it can start")


def version_string(port: int) -> str:
    """What browser this is, for the conditions a number is quoted under."""
    return str(_version(port).get("Browser", "unknown"))


def _version(port: int) -> dict[str, Any]:
    return json.loads(_get(f"http://127.0.0.1:{port}/json/version"))


def _get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=CALL_TIMEOUT_S) as response:
        return str(response.read().decode())


def _wait_for(port: int) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            _version(port)
        except urllib.error.URLError, OSError, json.JSONDecodeError:
            time.sleep(0.1)
        else:
            return
    raise CdpError(f"chromium never opened its debugging port {port}")
