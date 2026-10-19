"""A line the board says out loud: what was asked for, and what it keeps.

The length limit lives here rather than in the tool that takes the text. It is
one number, declared once, in the layer that already says what a request may
contain, and it is checked before Kokoro is asked for anything.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A paragraph, not a document. The voice is local and free, so this is not
# about a bill: it is about a session that pastes a page of output into speak
# and a room that has to sit through two minutes of it.
MAX_CHARS = 1000


class SpeechRequest(BaseModel):
    """A line to say, checked before anything is synthesised.

    Whitespace comes off first: a line that is nothing but spaces is nothing to
    say rather than a short one. An empty reason is no reason, so it is kept as
    nothing rather than as a string that says nothing.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=MAX_CHARS)
    voice: str | None = None
    reason: str | None = None

    @field_validator("voice", "reason")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None


class Spoken(BaseModel):
    """A line the board has said, and keeps so it can be read back or said again.

    `url` is how the page fetches the audio: an id, never a path. `reason` is
    whatever the caller said it was for, and is often nothing: a line a script
    sends on a schedule has no one to explain it.
    """

    id: str
    text: str
    voice: str
    reason: str | None = None
    url: str
    created_at: datetime
