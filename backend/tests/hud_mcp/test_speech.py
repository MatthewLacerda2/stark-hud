"""The speech tools as a session sees them: what it reads back after each call."""

import httpx
import pytest
from mcp.server.mcpserver import MCPServer

from core.config import Settings
from core.hub import hub
from hud_mcp.server import build_server
from repositories import speech as repo
from services import speech


@pytest.fixture
def server(monkeypatch, tmp_path) -> MCPServer:
    """Every tool registered, a Kokoro that always answers, and a quiet hub."""

    async def ignore(_event: str, _data: object) -> None:
        return None

    settings = lambda: Settings(SPEECH_DIR=str(tmp_path))  # noqa: E731
    monkeypatch.setattr(speech, "get_settings", settings)
    monkeypatch.setattr(repo, "get_settings", settings)
    monkeypatch.setattr(
        speech,
        "client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, content=b"mp3"))
        ),
    )
    monkeypatch.setattr(hub, "broadcast", ignore)
    return build_server()


async def call(server: MCPServer, name: str, **args: object) -> str:
    """Call a tool and return its text, the way an agent would see it."""
    result = await server.call_tool(name, args)
    return result.content[0].text


async def test_speak_says_which_voice_and_hands_back_the_id(server):
    said = await call(server, "speak", text="the build is green")

    line = repo.list_all()[0]
    assert said == f"Said out loud in af_heart (id {line.id}): the build is green"


async def test_list_spoken_reads_back_the_reason_and_the_text(server):
    assert await call(server, "list_spoken") == "The board has not said anything yet."
    await call(server, "speak", text="olá", voice="pf_dora", reason="deploy done")

    listed = await call(server, "list_spoken")
    assert "pf_dora — deploy done" in listed
    assert listed.endswith("olá")


async def test_replay_says_a_kept_line_again_and_refuses_an_unknown_one(server):
    await call(server, "speak", text="hello")
    line = repo.list_all()[0]

    assert await call(server, "replay", speech_id=line.id) == "Said again: hello"
    assert (await call(server, "replay", speech_id="nope")).startswith("Not replayed:")
