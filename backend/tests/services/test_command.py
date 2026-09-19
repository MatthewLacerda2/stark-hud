"""The two things Google refused on the first real prompt, pinned down.

No call to Gemini here, for the same reason `test_speech` never calls
ElevenLabs: a suite that spends money every `make check` is a bill. What broke
was on our side of the wire — a thinking level below a model's floor, and a
model turn rebuilt without the signature it came with — so that is what is
tested.
"""

from typing import get_args

from google.genai import types

from schemas.command import LEAST_THINKING, CommandModel
from services.command import _thinking, _turn


def test_every_model_on_the_menu_has_a_thinking_floor() -> None:
    assert set(get_args(CommandModel)) == set(LEAST_THINKING)


def test_flash_is_never_asked_for_less_than_low() -> None:
    config = _thinking("gemini-3.8-flash")
    assert config is not None
    assert config.thinking_level == types.ThinkingLevel.LOW


def test_flash_lite_goes_down_to_minimal() -> None:
    config = _thinking("gemini-3.5-flash-lite")
    assert config is not None
    assert config.thinking_level == types.ThinkingLevel.MINIMAL


def test_the_model_turn_goes_back_with_its_signature() -> None:
    signed = types.Part(
        function_call=types.FunctionCall(name="list_items", args={}),
        thought_signature=b"signed-by-google",
    )
    answer = types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[signed]))]
    )

    parts = _turn(answer).parts or []

    assert [p.thought_signature for p in parts] == [b"signed-by-google"]
