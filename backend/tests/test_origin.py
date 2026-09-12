"""The origin as it actually reaches a screen, over both surfaces.

`item.origin` is only ever an event. Nothing about it lands on an item, so the
socket is the only place it can be observed at all — and the absences matter as
much as the event does: a field that leaked into the persisted board would not
show up by looking at the television, which is how this board is reviewed.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from core.hub import hub
from hud_mcp.server import build_server
from main import app
from repositories import board as repo
from schemas.board import BoardSnapshot, ItemRead

NOTE = {"payload": {"kind": "note", "text": "hi"}}


class Listener:
    """A client that keeps whatever the hub pushed at it."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def accept(self) -> None:
        """The hub accepts a socket before it remembers it."""

    async def send_json(self, message: dict) -> None:
        """Record one broadcast."""
        self.messages.append(message)

    def events(self) -> list[str]:
        """The names of what arrived, in order."""
        return [m["event"] for m in self.messages]

    def origins(self) -> list[dict]:
        """Just the origins, as data."""
        return [m["data"] for m in self.messages if m["event"] == "item.origin"]


@pytest_asyncio.fixture
async def listening() -> Listener:
    """A connected client, dropped again when the test ends."""
    socket = Listener()
    await hub.connect(socket)
    yield socket
    await hub.disconnect(socket)


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTPX client bound to the ASGI app, the same one that ships."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_a_widget_made_by_a_tool_says_what_made_it(listening: Listener) -> None:
    """The call arrives beside the widget, and after it: the thing exists first."""
    await build_server().call_tool("add_note", {"text": "hi"})

    assert listening.events() == ["item.created", "item.origin"]
    origin = listening.origins()[0]
    assert set(origin) == {"id", "text"}
    assert origin["id"] == repo.list_items()[0].id
    assert origin["text"] == 'add_note(text="hi")'


async def test_nothing_about_an_origin_is_written_down(listening: Listener) -> None:
    """Never on the item, never in a snapshot, never in `board.hud`.

    A browser that connects a second later has missed it, and that is correct:
    an origin is an event and not a fact. This is the assertion that a field
    quietly leaking into the persisted board would fail.
    """
    await build_server().call_tool("add_note", {"text": "hi"})

    assert "origin" not in ItemRead.model_fields
    created = next(m for m in listening.messages if m["event"] == "item.created")
    assert "origin" not in created["data"]

    kept = BoardSnapshot(
        items=repo.list_items(), background=None, ink=None, notifications=[]
    ).model_dump_json()
    assert "origin" not in kept
    assert "add_note" not in kept


async def test_several_widgets_in_one_breath_do_not_pile_up(listening: Listener) -> None:
    """`arrange` and a board being rebuilt make several at once; the extras go.

    Every widget still arrives — only the texture is dropped, which is the whole
    reason dropping it is allowed.
    """
    server = build_server()
    for n in range(6):
        await server.call_tool("add_note", {"text": f"note {n}"})

    assert listening.events().count("item.created") == 6
    assert listening.events().count("item.origin") == 3


async def test_a_widget_created_over_http_says_so(client: AsyncClient, listening: Listener) -> None:
    """Otherwise this only happens while Claude is working, and half the board
    fills in silence: the agent writes its panels over HTTP."""
    await client.post("/api/v1/board/items", json=NOTE)

    text = listening.origins()[0]["text"]
    assert text.startswith("POST /api/v1/board/items ")
    assert '"kind": "note"' in text or '"kind":"note"' in text


async def test_a_panel_rewritten_on_a_schedule_fires_none_of_these(
    client: AsyncClient, listening: Listener
) -> None:
    """The agent rewrites panels every few seconds. On updates this would strobe,
    and a strobing board is one somebody turns off."""
    await client.put("/api/v1/board/items/by-key/cpu", json=NOTE)
    for _ in range(3):
        await client.put("/api/v1/board/items/by-key/cpu", json=NOTE)

    assert listening.events() == [
        "item.created",
        "item.origin",
        "item.updated",
        "item.updated",
        "item.updated",
    ]


@pytest.mark.parametrize("tool", ["list_items", "board_status"])
async def test_a_tool_that_makes_nothing_announces_nothing(tool: str, listening: Listener) -> None:
    """The seam sees every call; only a creation ever says anything."""
    await build_server().call_tool(tool, {})

    assert listening.events() == []
