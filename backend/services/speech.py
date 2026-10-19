"""The board's voice: have Kokoro read a line, keep it, and send it to the page.

Nothing here plays anything, and it cannot. The backend runs in a container with
no sound card; the only part of this board wired to a speaker is the browser
showing it. So this has the line synthesised, keeps the MP3 and its record, and
broadcasts where the page can fetch it. The page does the actual speaking.

Kokoro is a separate container speaking the OpenAI speech format, reached over
HTTP. It is local and free, so nothing here rations it, but it can be down —
stopped, still starting, or never deployed on this machine — and that comes back
as one sentence saying so, because the caller is a model reading tool output and
not a person reading a traceback.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from core.config import get_settings
from repositories import speech as repo
from schemas.speech import MAX_CHARS, SpeechRequest, Spoken
from services import events


class SpeechError(Exception):
    """Why nothing was said, in words the session can act on."""


def _checked(text: str, voice: str | None, reason: str | None) -> SpeechRequest:
    """The request, or a refusal saying why nothing was synthesised.

    A long line is never trimmed: half a sentence read aloud is worse than
    silence. The caller shortens it and asks again.
    """
    try:
        return SpeechRequest(text=text, voice=voice, reason=reason)
    except ValidationError as exc:
        if not text.strip():
            raise SpeechError("there is nothing to say.") from exc
        raise SpeechError(
            f"that line is {len(text)} characters and the board says at most "
            f"{MAX_CHARS}. Say the part worth interrupting somebody for."
        ) from exc


def client() -> httpx.AsyncClient:
    """The HTTP client Kokoro is reached through. A seam the tests replace."""
    return httpx.AsyncClient(timeout=get_settings().KOKORO_TIMEOUT_SECONDS)


def _complaint(response: httpx.Response) -> str:
    """What Kokoro said was wrong, as one line, whatever shape it said it in.

    FastAPI puts the reason in `detail`, which this server fills with a string,
    an object carrying a `message`, or a list of validation errors depending on
    what went wrong. Anything unreadable falls back to the start of the body.
    """
    try:
        body: Any = response.json()
    except ValueError:
        return response.text[:200] or "no reason given"
    detail = body.get("detail", body) if isinstance(body, dict) else body
    if isinstance(detail, dict):
        detail = detail.get("message") or detail.get("error") or detail
    return str(detail)[:200]


async def _synthesise(text: str, voice: str) -> bytes:
    """Have Kokoro read one line, and return the MP3."""
    url = get_settings().KOKORO_URL.rstrip("/")
    body = {
        "model": "kokoro",
        "input": text,
        "voice": voice,
        "response_format": "mp3",
        "stream": False,
    }
    try:
        async with client() as http:
            response = await http.post(f"{url}/v1/audio/speech", json=body)
    except httpx.TimeoutException as exc:
        raise SpeechError(
            f"Kokoro at {url} took too long to answer. If it was just started it "
            "may still be loading the model; try again in a minute."
        ) from exc
    except httpx.TransportError as exc:
        raise SpeechError(
            f"Kokoro is not answering at {url}, so the board has no voice right "
            "now. Its container is `kokoro` in docker-compose.yml; it may be "
            "stopped or not deployed yet."
        ) from exc
    if response.status_code != httpx.codes.OK:
        raise SpeechError(
            f"Kokoro refused the line ({response.status_code}): {_complaint(response)}"
        )
    return response.content


async def say(text: str, voice: str | None = None, reason: str | None = None) -> Spoken:
    """Synthesise one line, keep it, and send it to the page to be played.

    The line reaches the page from here. A line synthesised and not broadcast is
    one nobody hears, so the two are never separated.
    """
    request = _checked(text, voice, reason)
    chosen = request.voice or get_settings().KOKORO_VOICE
    audio = await _synthesise(request.text, chosen)
    speech_id = uuid.uuid4().hex
    line = Spoken(
        id=speech_id,
        text=request.text,
        voice=chosen,
        reason=request.reason,
        url=f"/api/v1/speech/{speech_id}",
        created_at=datetime.now(UTC),
    )
    repo.add(line, audio)
    await events.spoken(line)
    return line


async def replay(speech_id: str) -> Spoken:
    """Say a kept line again, from the audio already on disk.

    Nothing is synthesised: the same bytes are played, so a line sounds the same
    the second time and costs Kokoro nothing.
    """
    line = repo.get(speech_id)
    if line is None or repo.find_audio(speech_id) is None:
        raise SpeechError(
            f"there is no kept line with the id {speech_id!r}. The board keeps the "
            f"newest {get_settings().SPEECH_KEEP}; list_spoken shows which."
        )
    await events.spoken(line)
    return line
