"""A line the board says out loud: what was asked for, and what the page gets.

The length limit lives here rather than in the tool that takes the text. It is
one number, declared once, in the layer that already says what a request may
contain — and it is checked before anything is bought, so an over-long line
costs nothing and comes back as a sentence instead of being quietly trimmed.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# One breath, roughly: about six seconds of speech. The point of the ceiling is
# not the audio, it is the bill — this account has a few thousand characters a
# month, and a tool that will read a paragraph aloud is a tool that empties it.
MAX_CHARS = 100


class SpeechRequest(BaseModel):
    """A line to say, held to a length before the vendor is called.

    Whitespace comes off first: it is charged for like any other character, and
    a line that is nothing but spaces is nothing to say rather than a short one.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=MAX_CHARS)


class Spoken(BaseModel):
    """A line already synthesised, on its way to the browser to be played.

    `url` is how the page fetches the audio: an id, never a path. The text rides
    along so a client that cannot make a sound can still show what was said.
    """

    id: str
    text: str
    url: str
    created_at: datetime
