"""What made a widget appear, said once and then forgotten.

The board shows answers and never the asking. A gantt turns up; nothing on
screen ever says a session called ``add_gantt`` with four rows in it a moment
ago, so from the sofa the board is a thing that changes by itself — accurate,
and a little dead. This is the asking: the call that made a widget, drawn beside
it for about two seconds and then gone.

**Texture, not a log.** Nobody reads a JSON array of 200 chart points scrolling
past in two seconds from ten feet away, and nothing here is built as though they
might. It is the look of a machine being told what to do. So the text is cut
before the animation ever sees it, extras in a burst are dropped rather than
queued, and losing one costs nothing.

Nothing is written down: no field on an item, nothing in ``board.hud``, nothing
in a snapshot, nothing in ``ItemRead``. A browser that connects a second later
has missed it, and that is correct — an origin is an event and not a fact, which
is also why a page load does not fire a hundred of them.

Two halves. ``telling`` is what a surface sets when it still knows what it was
called with, and ``created`` is the only way a new widget reaches the socket — so
a creation cannot be announced without its origin coming with it, and not one of
the sixteen ``add_`` tools has to remember anything.
"""

import json
import time
from collections import deque
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from core.hub import hub
from schemas.board import ItemRead

# How long one of these is on screen. The frontend holds the same number as a
# motion token; it is here because it is also the width of the window below.
SECONDS = 2.0

# How many may be in the air at once. `arrange` and a board being rebuilt both
# create several widgets in one breath, and a tail of popups still appearing
# after the things they describe reads as a fault rather than as life — so above
# this the extras are dropped. Three is what fits beside three widgets without
# the screen becoming a wall of them.
AT_ONCE = 3

# The budget for the whole call, in characters. About four lines of the small
# dim panel this ends up in, which is as much as two seconds can carry past an
# eye that was never going to read it.
CHARS = 240

# And the budget for one argument, so a five-hundred-point chart cannot eat the
# whole line and leave every argument after it invisible. The names are most of
# what makes this read as a call, and they come last.
VALUE_CHARS = 72

# How much of an HTTP body is worth looking at before it is cut down. Well over
# the budget and small enough that a caller cannot make this expensive.
BODY_BYTES = 4096


def _cut(text: str, budget: int) -> str:
    """``text``, no longer than ``budget``, with an ellipsis where it was cut."""
    return text if len(text) <= budget else text[: budget - 1] + "…"


def _value(value: Any) -> str:
    """One argument, as it would have been written down.

    JSON rather than ``repr``: the arguments arrived as JSON, and ``"Tonight"``
    reads the same in both while ``{'kind': 'gantt'}`` does not.
    """
    return _cut(json.dumps(value, separators=(",", ":"), default=str), VALUE_CHARS)


def call(name: str, arguments: Mapping[str, Any]) -> str:
    """A tool call as a line of code: ``add_gantt(title="Tonight", rows=[…])``.

    A call and not a wire format. ``{"payload": {"kind": "gantt", …}}`` is what
    the board received; this is what somebody said, and the reference is a
    terminal echoing a command before it runs it.
    """
    said = ", ".join(f"{key}={_value(value)}" for key, value in arguments.items())
    return _cut(f"{name}({said})", CHARS)


def request(method: str, path: str, body: bytes) -> str:
    """An HTTP call as the line somebody would have typed at a terminal.

    A widget the agent writes over HTTP, or one a phone posts, gets an origin
    too — otherwise this is a thing that only happens while Claude is working,
    and half the board fills in silence.

    Whitespace is collapsed because a request pretty-printed by whoever sent it
    is still one call, and a call is one line.
    """
    sent = " ".join(body[:BODY_BYTES].decode("utf-8", "replace").split())
    return _cut(f"{method} {path} {sent}".rstrip(), CHARS)


_told: ContextVar[str | None] = ContextVar("origin", default=None)


@contextmanager
def telling(text: str) -> Iterator[None]:
    """Say what this call is, for exactly as long as it runs.

    A context variable rather than an argument because the place that knows the
    name is not the place that makes the widget, and the sixteen tools in
    between should not have to carry it. One surface sets this at its boundary
    and every widget made underneath picks it up.
    """
    token = _told.set(text)
    try:
        yield
    finally:
        _told.reset(token)


class Burst:
    """How many origins may be on screen at once, and nothing else.

    A window over what has been sent, not a queue of what is waiting. Texture
    that backs up is a tail of popups arriving after the widgets they describe,
    which is worse than the popups nobody sees — so this drops, and it never
    delays.
    """

    def __init__(self, most: int, seconds: float) -> None:
        self._most = most
        self._seconds = seconds
        self._sent: deque[float] = deque()

    def allows(self, now: float) -> bool:
        """Whether one more may go out now — and, if so, count it as gone."""
        while self._sent and now - self._sent[0] >= self._seconds:
            self._sent.popleft()
        if len(self._sent) >= self._most:
            return False
        self._sent.append(now)
        return True

    def clear(self) -> None:
        """Forget everything sent, so one test cannot silence the next."""
        self._sent.clear()


burst = Burst(AT_ONCE, SECONDS)


async def created(item: ItemRead) -> None:
    """Put a new widget on every screen, and say what made it.

    The only way a creation reaches the socket. Both broadcasts live here so a
    new ``add_`` tool, or a new route, cannot quietly arrive without one — there
    is no call site left that could forget, which is the whole reason this is a
    function rather than a convention.

    Creation only. A panel the agent rewrites every five seconds would strobe,
    and a strobing board is one somebody turns off; ``item.updated`` goes out
    from where it always did and carries none of this.
    """
    await hub.broadcast("item.created", item.model_dump(mode="json"))
    text = _told.get()
    if text is None or not burst.allows(time.monotonic()):
        return
    await hub.broadcast("item.origin", {"id": item.id, "text": text})
