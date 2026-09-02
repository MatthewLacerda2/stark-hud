"""The MCP tool that gives the board a voice.

The docstring below is the whole briefing. It is the only thing another session
will read before spending somebody's money, so it says what the tool costs and
what it refuses, not just what it does.
"""

from mcp.server.mcpserver import MCPServer

from core.hub import hub
from services import speech as service
from services.speech import SpeechError


def register(server: MCPServer) -> None:
    """Attach the speech tool to the server."""

    @server.tool()
    async def speak(text: str) -> str:
        """Say one short line out loud, through the television's speakers.

        **Use this judiciously.** The account is on a free tier with a few
        thousand characters a month, and every call spends real quota that does
        not come back until it resets. Speaking is for something worth
        interrupting a room for — a build finished that somebody is waiting on,
        a warning nobody is looking at the screen to see. It is not for
        narrating what a tool has already handed back as text: whoever asked is
        reading that, and the board has notify and widgets for the rest.

        Nobody has to be looking at the board for this to land, and nobody can
        replay it. Say the thing itself, not that there is a thing.

        **At most 100 characters.** Over that is refused, not trimmed: half a
        sentence read aloud to a room is worse than silence, and it would still
        be charged for. Shorten it yourself and call again.

        **A voice labelled English reads other languages perfectly well.** Write
        the line in whatever language the user speaks and pass it straight in.
        Do not go looking for a Portuguese voice to say a Portuguese line, and
        do not avoid this tool because what you want to say is not in English.

        Failures come back as a sentence saying what to do, including the one
        that will eventually happen on this account: running out of characters.
        """
        try:
            spoken = await service.say(text)
        except SpeechError as exc:
            return f"Not spoken: {exc}"
        await hub.broadcast("speech.spoken", spoken.model_dump(mode="json"))
        return f"Said out loud: {spoken.text}"
