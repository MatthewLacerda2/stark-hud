"""The speak tool: what the room hears, and what the session reads back.

The vendor is mocked here for the same reason it is in the service tests — the
account has a few thousand characters a month — but what is being checked is
different. This is the seam between a tool call and a television: the backend
has no sound card, so a line is only ever spoken if the broadcast carries
something the page can play.
"""

from types import SimpleNamespace

import pytest
from elevenlabs.core.api_error import ApiError
from mcp.server.mcpserver import MCPServer

from core.config import Settings
from core.hub import hub
from hud_mcp.server import build_server
from services import speech


@pytest.fixture
def server() -> MCPServer:
    """A server with every tool registered."""
    return build_server()


@pytest.fixture
def said(monkeypatch, tmp_path):
    """A working voice and a hub that keeps what it was told to broadcast."""
    box = SimpleNamespace(events=[], error=None)

    class FakeSpeech:
        def convert(self, **_kwargs: object) -> object:
            if box.error is not None:
                raise box.error
            return iter([b"\xff\xfbpretend mp3"])

    class FakeClient:
        def __init__(self, *, api_key: str | None = None) -> None:
            self.text_to_speech = FakeSpeech()

    async def record(event: str, data: object) -> None:
        box.events.append((event, data))

    monkeypatch.setattr(speech, "ElevenLabs", FakeClient)
    monkeypatch.setattr(
        speech,
        "get_settings",
        lambda: Settings(SPEECH_DIR=str(tmp_path), ELEVENLABS_API_KEY="a-key"),
    )
    monkeypatch.setattr(hub, "broadcast", record)
    return box


async def call(server: MCPServer, name: str, **args: object) -> str:
    """Call a tool and return its text, the way an agent would see it."""
    result = await server.call_tool(name, args)
    return result.content[0].text


async def test_the_broadcast_carries_something_the_page_can_play(server, said) -> None:
    """The backend has no speakers. The browser does, and this is all it is given."""
    assert "Said out loud" in await call(server, "speak", text="The build is green.")
    event, data = said.events[0]
    assert event == "speech.spoken"
    assert data["url"] == f"/api/v1/speech/{data['id']}"
    assert data["text"] == "The build is green."
    assert speech.audio_path(data["id"]) is not None


async def test_a_long_line_comes_back_as_a_sentence_and_is_never_said(server, said) -> None:
    """The tool refuses in the house style rather than raising or trimming."""
    message = await call(server, "speak", text="x" * 101)
    assert message.startswith("Not spoken:")
    assert "101 characters" in message
    assert said.events == []


async def test_an_empty_quota_reads_as_running_out(server, said) -> None:
    """The one failure this account will certainly meet, said as a fact."""
    said.error = ApiError(
        status_code=401,
        body={"detail": {"status": "quota_exceeded", "message": "0 characters remaining"}},
    )
    message = await call(server, "speak", text="The build is green.")
    assert message.startswith("Not spoken:")
    assert "run out of characters" in message
    assert said.events == []
