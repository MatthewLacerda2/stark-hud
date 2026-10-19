"""The voice: what is asked of Kokoro, what is kept, and what reaches the page.

Kokoro is replaced by an in-process transport, so these run without the
container and check the seam that matters: a line is only ever heard if the
broadcast carries something the page can play, and only ever found again if the
record and its audio were kept together.
"""

import json
from types import SimpleNamespace

import httpx
import pytest

from core.config import Settings
from core.hub import hub
from repositories import speech as repo
from services import speech
from services.speech import SpeechError


@pytest.fixture
def kokoro(monkeypatch, tmp_path):
    """A Kokoro that answers with pretend MP3, and a hub that keeps its broadcasts."""
    box = SimpleNamespace(asked=[], events=[], answer=None, keep=100)

    def handle(request: httpx.Request) -> httpx.Response:
        box.asked.append(json.loads(request.content))
        if box.answer is not None:
            return box.answer(request)
        return httpx.Response(200, content=b"\xff\xfbpretend mp3")

    async def record(event: str, data: object) -> None:
        box.events.append((event, data))

    settings = lambda: Settings(SPEECH_DIR=str(tmp_path), SPEECH_KEEP=box.keep)  # noqa: E731
    monkeypatch.setattr(speech, "get_settings", settings)
    monkeypatch.setattr(repo, "get_settings", settings)
    monkeypatch.setattr(
        speech, "client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handle))
    )
    monkeypatch.setattr(hub, "broadcast", record)
    return box


async def test_a_line_is_read_in_the_default_voice_kept_and_sent_to_the_page(kokoro):
    line = await speech.say("the build is green", reason="  ")

    assert kokoro.asked[0]["input"] == "the build is green"
    assert kokoro.asked[0]["voice"] == "af_heart"
    assert line.reason is None  # a blank reason is no reason
    assert repo.find_audio(line.id) is not None
    event, data = kokoro.events[0]
    assert event == "speech.spoken"
    assert data["url"] == f"/api/v1/speech/{line.id}"
    assert data["play"]


async def test_a_named_voice_and_a_reason_are_kept_with_the_line(kokoro):
    line = await speech.say("olá", voice="pf_dora", reason="build finished")

    assert kokoro.asked[0]["voice"] == "pf_dora"
    assert repo.list_all()[0].reason == "build finished"
    assert line.voice == "pf_dora"


async def test_the_oldest_line_goes_record_and_audio_together(kokoro):
    kokoro.keep = 2
    first = await speech.say("one")
    await speech.say("two")
    await speech.say("three")

    assert [line.text for line in repo.list_all()] == ["three", "two"]
    assert repo.get(first.id) is None
    assert repo.find_audio(first.id) is None


async def test_a_kokoro_that_is_down_is_said_in_one_sentence(kokoro):
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    kokoro.answer = down
    with pytest.raises(SpeechError, match="not answering"):
        await speech.say("hello")
    assert repo.list_all() == []
    assert kokoro.events == []


async def test_what_kokoro_refuses_comes_back_in_its_own_words(kokoro):
    kokoro.answer = lambda _r: httpx.Response(
        400, json={"detail": {"error": "validation_error", "message": "Voice 'xx' not found"}}
    )
    with pytest.raises(SpeechError, match="Voice 'xx' not found"):
        await speech.say("hello", voice="xx")


async def test_nothing_and_too_much_are_refused_before_kokoro_is_asked(kokoro):
    with pytest.raises(SpeechError, match="nothing to say"):
        await speech.say("   ")
    with pytest.raises(SpeechError, match="at most"):
        await speech.say("a" * 1001)
    assert kokoro.asked == []


async def test_a_replay_is_the_same_line_as_a_new_broadcast(kokoro):
    line = await speech.say("hello")
    again = await speech.replay(line.id)

    assert again.id == line.id
    assert len(kokoro.asked) == 1  # nothing synthesised the second time
    first, second = (data for _event, data in kokoro.events)
    assert first["id"] == second["id"]
    assert first["play"] != second["play"]


async def test_replaying_a_line_that_is_not_kept_is_refused(kokoro):
    with pytest.raises(SpeechError, match="list_spoken"):
        await speech.replay("0" * 32)
