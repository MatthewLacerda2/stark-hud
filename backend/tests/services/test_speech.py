"""Buying a line of speech, without ever buying one.

The vendor is mocked in every test here, and deliberately. The account this
board speaks from has a few thousand characters a month and a human watching
them go; a suite that called the real thing would be a bill that grows every
time somebody runs `make check`.

What is worth pinning down is not the HTTP call — the SDK owns that — but the
translation on either side of it: what is refused before a character is spent,
and what a session is told when the vendor says no. The 401 is the reason this
file exists. Two of them mean opposite things, and telling them apart wrongly
sends a person to change a credential that was never wrong.
"""

import os
from types import SimpleNamespace

import pytest
from elevenlabs.core.api_error import ApiError

from core.config import Settings
from schemas.speech import MAX_CHARS
from services import speech
from services.speech import SpeechError


def _api_error(status_code: int, detail: object) -> ApiError:
    """An error shaped the way the vendor's really are."""
    return ApiError(status_code=status_code, body={"detail": detail})


@pytest.fixture
def vendor(monkeypatch, tmp_path):
    """A configured board with a fake ElevenLabs behind it.

    The box that comes back is the vendor's script: set `error` and the next
    call raises it, read `calls` to see what it was asked for.
    """
    box = SimpleNamespace(audio=b"\xff\xfbpretend mp3", error=None, calls=[], keep=20, key="a-key")

    class FakeSpeech:
        def convert(self, **kwargs: object) -> object:
            box.calls.append(kwargs)
            if box.error is not None:
                raise box.error
            return iter([box.audio[:3], box.audio[3:]])

    class FakeClient:
        def __init__(self, *, api_key: str | None = None) -> None:
            box.used_key = api_key
            self.text_to_speech = FakeSpeech()

    monkeypatch.setattr(speech, "ElevenLabs", FakeClient)
    monkeypatch.setattr(
        speech,
        "get_settings",
        lambda: Settings(
            SPEECH_DIR=str(tmp_path), SPEECH_KEEP=box.keep, ELEVENLABS_API_KEY=box.key
        ),
    )
    box.folder = tmp_path
    return box


async def test_a_line_is_bought_in_the_voice_and_model_that_were_settled_on(vendor) -> None:
    """Not a literal buried in a call: the voice and the price are configuration."""
    spoken = await speech.say("Build's green.")
    # George, chosen by ear. A literal rather than the setting: this test
    # exists to make changing the voice a deliberate act, and one that
    # reads the setting back would agree with any value at all.
    assert vendor.calls[0]["voice_id"] == "JBFqnCBsd6RMkjVDRZzb"
    assert vendor.calls[0]["model_id"] == "eleven_flash_v2_5"
    assert vendor.calls[0]["text"] == "Build's green."
    assert spoken.text == "Build's green."


async def test_the_voice_settings_are_sent_and_not_left_to_the_vendor(vendor) -> None:
    """Sending nothing lets ElevenLabs pick, and what it picks is theirs to change."""
    await speech.say("Build's green.")
    sent = vendor.calls[0]["voice_settings"]
    assert (sent.stability, sent.similarity_boost, sent.style) == (0.5, 0.75, 0.0)
    assert sent.use_speaker_boost is True
    assert sent.speed == 0.95


async def test_what_the_page_is_handed_is_a_url_and_never_a_path(vendor) -> None:
    """An id is the handle, the way every other file this API serves is addressed."""
    spoken = await speech.say("Build's green.")
    assert spoken.url == f"/api/v1/speech/{spoken.id}"
    assert str(vendor.folder) not in spoken.url
    assert speech.audio_path(spoken.id).read_bytes() == vendor.audio


async def test_a_long_line_is_refused_before_a_character_is_spent(vendor) -> None:
    """Refused, not trimmed: half a sentence read to a room is worse than silence."""
    with pytest.raises(SpeechError) as refused:
        await speech.say("x" * (MAX_CHARS + 1))
    assert f"{MAX_CHARS + 1} characters" in str(refused.value)
    assert str(MAX_CHARS) in str(refused.value)
    assert vendor.calls == []


async def test_an_empty_line_is_refused_too(vendor) -> None:
    """Nothing to say is not a failure to explain at length."""
    with pytest.raises(SpeechError, match="nothing to say"):
        await speech.say("   ")
    assert vendor.calls == []


async def test_a_missing_key_is_not_the_same_problem_as_a_key_missing_a_scope(
    vendor,
) -> None:
    """The two 401s this vendor sends have opposite fixes, and must read that way."""
    vendor.key = ""
    with pytest.raises(SpeechError) as absent:
        await speech.say("Build's green.")

    vendor.key = "a-key"
    vendor.error = _api_error(
        401, {"status": "missing_permissions", "message": "requires text_to_speech"}
    )
    with pytest.raises(SpeechError) as scoped:
        await speech.say("Build's green.")

    assert "ELEVENLABS_API_KEY" in str(absent.value)
    # The key is fine. Nobody should be sent to look at it.
    assert "valid" in str(scoped.value)
    assert "dashboard" in str(scoped.value)
    assert "requires text_to_speech" in str(scoped.value)
    assert str(absent.value) != str(scoped.value)


async def test_a_key_the_vendor_rejects_points_at_the_env_file(vendor) -> None:
    """A 401 with no status behind it is the ordinary wrong-credential kind."""
    vendor.error = _api_error(401, {"message": "invalid api key"})
    with pytest.raises(SpeechError, match="rejected the key itself"):
        await speech.say("Build's green.")


async def test_running_out_of_characters_says_so_plainly(vendor) -> None:
    """It will happen on this account, so it reads as a fact and not as a fault."""
    vendor.error = _api_error(
        401, {"status": "quota_exceeded", "message": "0 characters remaining"}
    )
    with pytest.raises(SpeechError) as out:
        await speech.say("Build's green.")
    assert "run out of characters" in str(out.value)
    assert "0 characters remaining" in str(out.value)


async def test_a_paid_plan_is_named_as_the_reason(vendor) -> None:
    """The third thing this free-tier account hears back."""
    vendor.error = _api_error(401, {"status": "paid_plan_required", "message": "upgrade"})
    with pytest.raises(SpeechError, match="paid plan"):
        await speech.say("Build's green.")


async def test_a_detail_that_is_an_array_does_not_crash_the_parse(vendor) -> None:
    """A validation failure puts a list where the status usually is."""
    vendor.error = _api_error(422, [{"loc": ["body", "text"], "msg": "too long"}])
    with pytest.raises(SpeechError, match="422"):
        await speech.say("Build's green.")


async def test_the_vendor_being_unreachable_is_also_a_sentence(vendor) -> None:
    """No exception reaches the session: it gets something it can read."""
    vendor.error = ConnectionError("name or service not known")
    with pytest.raises(SpeechError, match="could not be reached"):
        await speech.say("Build's green.")


async def test_only_the_newest_lines_are_kept(vendor) -> None:
    """A board that never deletes fills a disk on a machine nobody logs into."""
    vendor.keep = 2
    first = await speech.say("one")
    os.utime(speech.audio_path(first.id), (1000, 1000))
    second = await speech.say("two")
    os.utime(speech.audio_path(second.id), (2000, 2000))
    third = await speech.say("three")

    assert len(list(vendor.folder.glob("*.mp3"))) == 2
    assert speech.audio_path(first.id) is None
    assert speech.audio_path(second.id) is not None
    assert speech.audio_path(third.id) is not None


async def test_two_lines_close_together_are_two_files(vendor) -> None:
    """Neither overwrites the other, so neither can be played as the wrong bytes."""
    one = await speech.say("one")
    two = await speech.say("two")
    assert one.id != two.id
    assert one.url != two.url
    assert len(list(vendor.folder.glob("*.mp3"))) == 2


async def test_an_id_that_is_really_a_path_is_not_a_line(vendor) -> None:
    """It arrives in a URL, so it is checked rather than trusted."""
    assert speech.audio_path("../../board.hud") is None
    assert speech.audio_path("not-a-uuid") is None
