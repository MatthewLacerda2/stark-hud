"""The board's voice: buy a line of speech, and put it where the page can play it.

Nothing here plays anything, and it cannot. The backend runs in a container with
no sound card; the only thing on this board wired to the television's speakers is
the browser showing it. So this synthesises the line, writes the MP3 into a
directory the API serves by id, and hands back a record for the socket to
broadcast. The page does the actual speaking.

Everything that can go wrong comes back as a `SpeechError` carrying one sentence
about what to do, because the caller is a model reading tool output and not a
person reading a traceback.

The vendor's 401 is why that matters. It means two opposite things:

  * `detail.status == "missing_permissions"` — the key is perfectly good and is
    merely missing a scope. The body names which one, and the fix is a checkbox
    in the ElevenLabs dashboard.
  * no key, or a wrong one — the fix is in `.env`.

Reporting the first as the second sends somebody to stare at a credential that
is already correct, so the status is read before the status code, and `detail`
is parsed defensively: a validation failure puts an array there instead of an
object, and it carries no status at all.
"""

import asyncio
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.types import VoiceSettings
from pydantic import ValidationError

from core.config import Settings, get_settings
from schemas.speech import MAX_CHARS, SpeechRequest, Spoken

# The audio the television gets. 128 kbps MP3 is the cheapest format the free
# tier will produce and far past what a spoken sentence needs; anything better
# would only be bytes the browser has to fetch before it can say anything.
OUTPUT_FORMAT = "mp3_44100_128"

# An id is a uuid and nothing else. It arrives in a URL and is turned into a
# filename, so it is checked rather than trusted: `../../board.hud` is a path,
# not a line the board once said.
_ID = re.compile(r"[0-9a-f]{32}")


class SpeechError(Exception):
    """Why nothing was said, in words the session can act on."""


NO_KEY = (
    "there is no ELEVENLABS_API_KEY in the backend's environment, so the board "
    "has no voice at all. Put the key in the .env beside docker-compose.yml and "
    "restart the backend."
)

BAD_KEY = (
    "ElevenLabs rejected the key itself. The one in the .env beside "
    "docker-compose.yml is wrong, expired, or belongs to another account."
)

# Keyed on what the vendor calls the failure, not on the status code it came
# with, because several of these arrive as the same 401 and mean entirely
# different things.
_REFUSALS = {
    "missing_permissions": (
        "the ElevenLabs key is valid but lacks a permission — {message}. Nothing "
        "in .env needs changing: grant that permission to the key in the "
        "ElevenLabs dashboard."
    ),
    "quota_exceeded": (
        "the ElevenLabs account has run out of characters for the month — "
        "{message}. Nothing is broken and there is nothing to fix; the quota "
        "comes back when it resets."
    ),
    "paid_plan_required": (
        "ElevenLabs will only do this on a paid plan — {message}. This account "
        "is on the free tier, so the board cannot say it."
    ),
}


def _detail(body: Any) -> tuple[str, str]:
    """The vendor's own name for what went wrong, and its explanation.

    `detail` is an object for every failure worth telling apart, and an array
    for a validation failure — a different shape carrying no status. Anything
    that is not an object is read as "no status", and the caller falls back to
    the status code.
    """
    detail = body.get("detail") if isinstance(body, dict) else None
    if not isinstance(detail, dict):
        return "", ""
    return str(detail.get("status") or ""), str(detail.get("message") or "")


def _refusal(exc: ApiError) -> str:
    """Turn an ElevenLabs error into the one sentence a session should read."""
    status, message = _detail(exc.body)
    if status in _REFUSALS:
        return _REFUSALS[status].format(message=message or "no reason given")
    if exc.status_code == 401:
        return BAD_KEY
    said = message or status or str(exc.body)
    return f"ElevenLabs answered {exc.status_code}: {said}"


def _checked(text: str) -> str:
    """The line, or a refusal saying why nothing was bought.

    The limit is on the schema, so this only has to say what a caller should do
    about it. A long line is never trimmed: half a sentence read aloud to a room
    is worse than silence, and it would be charged for.
    """
    try:
        return SpeechRequest(text=text).text
    except ValidationError as exc:
        if not text.strip():
            raise SpeechError("there is nothing to say.") from exc
        raise SpeechError(
            f"that line is {len(text)} characters and the board says at most "
            f"{MAX_CHARS}. Shorten it to the part worth interrupting a room for."
        ) from exc


def _voice(settings: Settings) -> VoiceSettings:
    """How the line is to be read, said out of configuration rather than left open.

    Sending nothing here is not the same as sending the defaults: it lets the
    vendor pick, and what it picks is theirs to change. These are the same
    numbers, but they are ours, and `core.config` says which one is not the
    vendor's and why.
    """
    return VoiceSettings(
        stability=settings.ELEVENLABS_STABILITY,
        similarity_boost=settings.ELEVENLABS_SIMILARITY_BOOST,
        style=settings.ELEVENLABS_STYLE,
        use_speaker_boost=settings.ELEVENLABS_USE_SPEAKER_BOOST,
        speed=settings.ELEVENLABS_SPEED,
    )


def _convert(text: str) -> bytes:
    """Buy the audio for one line. Blocking, so it is called off the event loop.

    The SDK streams the MP3 back in chunks; the whole line is a few seconds and
    is joined here, because what the page plays is a file at a URL and not a
    stream.

    A line the board has said before does not come back here at all in any real
    sense: the vendor caches on the text, the voice and the model, answers a
    repeat instantly, and does not appear to charge for it. The voice settings
    are not part of that key, so a sentence already spoken keeps the speed it was
    first spoken at no matter what is sent below. That is the trap in tuning
    these values, and `core.config` says so where somebody would change them.
    """
    settings = get_settings()
    client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    try:
        chunks = client.text_to_speech.convert(
            voice_id=settings.ELEVENLABS_VOICE_ID,
            model_id=settings.ELEVENLABS_MODEL_ID,
            output_format=OUTPUT_FORMAT,
            voice_settings=_voice(settings),
            text=text,
        )
        return b"".join(chunks)
    except ApiError as exc:
        raise SpeechError(_refusal(exc)) from exc
    except Exception as exc:
        raise SpeechError(f"ElevenLabs could not be reached: {exc}") from exc


def folder() -> Path:
    """The directory spoken lines are kept in, made if it is not there yet."""
    path = Path(get_settings().SPEECH_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def audio_path(speech_id: str) -> Path | None:
    """The MP3 for a line, or nothing when it was never said or has aged out."""
    if not _ID.fullmatch(speech_id):
        return None
    target = folder() / f"{speech_id}.mp3"
    return target if target.is_file() else None


def _prune(keep: int) -> None:
    """Delete all but the newest few lines.

    A line cannot be deleted the moment it is broadcast — the browser has not
    fetched it yet — and a board that never deletes them fills a disk on a
    machine nobody logs into. Keeping a handful is the middle: a line stays
    fetchable long after the moment to say it has passed, and the directory has
    a ceiling it never grows past.
    """
    said = sorted(folder().glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in said[keep:]:
        stale.unlink(missing_ok=True)


def _store(text: str, audio: bytes) -> Spoken:
    """Write the MP3 down under a fresh id and say where the page can get it.

    A fresh id per line, rather than a name derived from the text, is what lets
    two lines spoken a second apart be two files and two URLs: neither overwrites
    the other, and the browser can never be handed the wrong bytes from a cache.
    """
    speech_id = uuid.uuid4().hex
    (folder() / f"{speech_id}.mp3").write_bytes(audio)
    _prune(get_settings().SPEECH_KEEP)
    return Spoken(
        id=speech_id,
        text=text,
        url=f"/api/v1/speech/{speech_id}",
        created_at=datetime.now(UTC),
    )


async def say(text: str) -> Spoken:
    """Synthesise one line and keep it, ready for the page to play.

    The vendor call is blocking and takes a second or two, so it runs in a
    thread: the same event loop carries every socket looking at this board, and
    a board that stops repainting while it buys a sentence is worse than a board
    that says nothing.
    """
    line = _checked(text)
    if not get_settings().ELEVENLABS_API_KEY:
        raise SpeechError(NO_KEY)
    audio = await asyncio.to_thread(_convert, line)
    return _store(line, audio)
