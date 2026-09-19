"""What a typed instruction is, and what comes back from having run it.

Not a payload and not a widget: nothing here is ever drawn or stored. A command
is a sentence somebody typed at the board, the tool calls it turned into, and
then nothing — the board itself is the answer, and if a widget moved you saw it
move. What comes back exists so the bar knows the work happened and can say one
sentence when it did not.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The models a prompt may be sent to, as the Gemini docs read on 2026-09-13.
#
# Two, and both Flash: the whole reason this path exists beside Claude is that a
# small imperative change should not cost a large model's turn. Prices are per
# million tokens, input / output.
#
#   gemini-3.5-flash-lite   $0.30 / $2.50   the default
#   gemini-3.8-flash        $0.75 / $3.75   for a sentence the small one gets wrong
#
# 2.5 Flash Lite was on this menu and came off it: cheapest, but nobody picked
# it, and a menu of two is a quicker choice at a keyboard.
#
# The Live API is deliberately not here. It is a stateful WebSocket built for
# real-time audio, its tool calls have to be answered by hand, and it costs more
# for text — none of which buys anything for a typed one-shot. The day the board
# should be talked to rather than typed at, it is the right answer and it is its
# own piece of work.
CommandModel = Literal[
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
]

# How little each model may be asked to think. Both think before answering, and
# on a menu whose entire purpose is speed the dial goes as low as it turns — but
# how low that is differs per model, and Google refuses a request below the
# floor with a 400 rather than rounding up. 3.8 Flash stops at LOW; asking it
# for MINIMAL is exactly that refusal.
LEAST_THINKING: dict[str, Literal["MINIMAL", "LOW"]] = {
    "gemini-3.5-flash-lite": "MINIMAL",
    "gemini-3.8-flash": "LOW",
}


class CommandRequest(BaseModel):
    """One instruction typed at the board."""

    model_config = ConfigDict(extra="forbid")

    # Long enough for a sentence with three widgets named in it, short enough
    # that nobody pastes a document into the board's address bar. Refused rather
    # than truncated: a half-read instruction does half of what was asked, and
    # half of a board change is worse than none.
    prompt: str = Field(min_length=1, max_length=2000)

    # Left out, the server's own default is used. The bar sends one because it
    # has a dropdown; anything else driving this endpoint should not have to
    # know what models exist.
    model: CommandModel | None = None


class CommandCall(BaseModel):
    """One tool the model called, and the sentence that tool answered with."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    # What the tool returned, which for every tool on this board is one line of
    # plain English meant to be read by the model that called it. Passed back
    # untouched rather than parsed: it is the honest record of what happened,
    # and a refusal reads the same way as a success.
    said: str


class CommandRead(BaseModel):
    """What running an instruction did.

    For the bar, not for a person. Nothing here is drawn on the board — the
    board already changed, which is the point.
    """

    model_config = ConfigDict(extra="forbid")

    model: str
    calls: list[CommandCall]
    # Wall clock for the whole thing, including every round trip to Google. The
    # number this feature is judged by, so it comes back on every response
    # rather than only into a log nobody on the sofa is reading.
    took_ms: int
