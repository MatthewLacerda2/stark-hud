"""The MCP tools that give the board a voice, and remember what it said.

The docstrings below are the whole briefing another session reads, so they say
when speaking is worth it and which voices exist, not just what each call does.
"""

from mcp.server.mcpserver import MCPServer

from repositories import speech as repo
from schemas.speech import Spoken
from services import speech as service
from services.speech import SpeechError


def _line(line: Spoken) -> str:
    """One kept line as a session reads it back: enough to pick it out and replay it."""
    when = line.created_at.astimezone().strftime("%Y-%m-%d %H:%M")
    why = f" — {line.reason}" if line.reason else ""
    return f"{line.id} · {when} · {line.voice}{why}\n    {line.text}"


def register(server: MCPServer) -> None:
    """Attach the speech tools to the server."""

    @server.tool()
    async def speak(text: str, voice: str | None = None, reason: str | None = None) -> str:
        """Say a line out loud, through the speakers of whatever is showing the board.

        It plays at once on every open board tab. With none open, nobody hears it
        now, but it is kept: the board remembers its newest hundred lines, and
        list_spoken and replay find one again later. So say the thing itself, not
        that there is a thing.

        The voice is a local model and costs nothing, but a voice still
        interrupts somebody. Speak for something worth that: a long job finished
        that someone is waiting on, a warning nobody is looking at the screen to
        see. Not to read back what a tool already returned as text, and not to
        narrate your work. Use notify for the rest.

        `voice` is optional, and defaults to af_heart (American English). The
        voice decides the accent, not the text: an English voice reads
        Portuguese passably and a native one reads it better. Good ones —
        English: af_heart, af_bella, am_michael, am_fenrir, bf_emma (British),
        bm_george (British). Brazilian Portuguese: pf_dora, pm_alex, pm_santa.
        Spanish ef_dora, French ff_siwis, Italian if_sara, Japanese jf_alpha.

        `reason` is a few words on why this was said, kept beside the line so a
        later session can tell how it came to be there. Optional, and worth
        giving.

        At most 1000 characters, refused rather than trimmed. Failures come back
        as one sentence saying what to do, including Kokoro being down.
        """
        try:
            line = await service.say(text, voice, reason)
        except SpeechError as exc:
            return f"Not spoken: {exc}"
        return f"Said out loud in {line.voice} (id {line.id}): {line.text}"

    @server.tool()
    async def list_spoken(limit: int = 20) -> str:
        """Read back what the board has said, newest first.

        Each line gives its id (for replay), when, the voice, the reason if one
        was given, and the text. The board keeps its newest hundred.
        """
        lines = repo.list_all()[: max(limit, 1)]
        if not lines:
            return "The board has not said anything yet."
        return "\n".join(_line(line) for line in lines)

    @server.tool()
    async def replay(speech_id: str) -> str:
        """Say a kept line again on every open board tab, exactly as it sounded.

        Nothing is synthesised again. The id comes from list_spoken or from what
        speak returned.
        """
        try:
            line = await service.replay(speech_id)
        except SpeechError as exc:
            return f"Not replayed: {exc}"
        return f"Said again: {line.text}"
