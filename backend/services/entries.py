"""Adding one line to a widget that is kept rather than recomputed.

Two widgets on this board hold what they were given instead of being rewritten
whole: a list somebody keeps, and a countdown stack. Both are built up an entry
at a time by sessions that never saw the other entries, so "write the payload
again" is not available — it would mean knowing every entry already there and
losing the ones you did not.

That rule used to live inside ``hud_mcp/lists.py`` and ``hud_mcp/countdowns.py``,
which made appending a thing only an MCP client could do: the agent feeding the
panels over HTTP could rewrite a list whole or nothing, and rewriting whole is
exactly what a kept list cannot survive. It is board behaviour and not a way in,
so it is here, and the route and the two tools are all thin over it.

One module for both kinds, because it is one behaviour. Which fields of an entry
mean anything is decided by the widget: a ``start`` on a list, or a body colour
on a countdown, comes back as a sentence rather than being quietly dropped.
"""

from schemas.board import Countdown, CountdownPayload, ItemRead, ItemUpdate, ListEntry, ListPayload
from schemas.entries import EntryCreate
from services import board as service

# The two payloads that keep what they are given. Anything else on this board is
# written whole and has no entries to add one to.
Kept = ListPayload | CountdownPayload
Entry = str | ListEntry | Countdown


class NotKeptError(Exception):
    """Raised when a widget that is written whole is asked to keep one more line.

    Named with the widget's kind, because a caller that lands here almost always
    has the wrong id rather than the wrong idea — and the answer is either
    ``add_list`` / ``add_countdown`` to make one, or writing the payload again
    for a widget that is recomputed.
    """

    def __init__(self, item: ItemRead) -> None:
        self.item = item
        super().__init__(
            f"{item.id} is a {item.payload.kind}, which is written whole rather than "
            f"added to. Only a list and a countdown keep their entries."
        )


class BadEntryError(Exception):
    """Raised when a line does not fit the widget it was addressed to.

    A countdown entry without a ``start`` is not a countdown, and a list line
    with one is somebody aiming at the wrong widget. Both are said out loud: a
    field dropped in silence is a session that thinks it wrote something.
    """


class NoEntryError(Exception):
    """Raised when the line named for removal is not one this widget holds.

    What it does hold is named, because the text is matched as it reads on the
    screen and getting it slightly wrong is the ordinary mistake.
    """

    def __init__(self, item: ItemRead, title: str, held: list[str]) -> None:
        self.item = item
        self.title = title
        self.held = held
        named = ", ".join(repr(t) for t in held) or "nothing"
        super().__init__(f"No entry {title!r} in {item.id}. It holds: {named}")


def kept(item: ItemRead) -> Kept:
    """This widget's payload, when it is one that keeps its entries.

    The payload comes back rather than a yes, because a caller handed only the
    item would then be reading ``.items`` off a union of thirteen payload kinds,
    most of which have no such field. The check happened; this is it saying so.
    """
    if not isinstance(item.payload, ListPayload | CountdownPayload):
        raise NotKeptError(item)
    return item.payload


def title_of(entry: Entry) -> str:
    """The line as it reads on the screen, whichever shape the entry has."""
    return entry if isinstance(entry, str) else entry.title


def _for_list(data: EntryCreate) -> Entry:
    """One line of a list. A bare title stays a bare string.

    A list of plain lines stays one: something that printed those lines will
    rewrite them whole, and a single ``ListEntry`` in the middle would make that
    a list of two shapes for no gain.
    """
    if data.start is not None or data.end is not None:
        raise BadEntryError(
            "A list line has no start or end. Those belong to a countdown — "
            "add_countdown makes one."
        )
    extras = (data.body, data.icon, data.title_color, data.body_color, data.icon_color)
    if all(extra is None for extra in extras):
        return data.title
    return ListEntry(
        title=data.title,
        body=data.body,
        icon=data.icon,
        title_color=data.title_color,
        body_color=data.body_color,
        icon_color=data.icon_color,
    )


def _for_countdown(data: EntryCreate) -> Entry:
    """One thing on a countdown stack, which is a title and when it happens."""
    if data.start is None:
        raise BadEntryError(
            f"{data.title!r} needs a start: a countdown counts down to something. "
            f"Both ends are ISO 8601, and without a zone they are this machine's time."
        )
    if data.body is not None:
        raise BadEntryError("A countdown entry has no body — only a title, an icon and its ends.")
    return Countdown(title=data.title, icon=data.icon, start=data.start, end=data.end)


def built(item: ItemRead, data: EntryCreate) -> Entry:
    """The entry this widget would hold, or a refusal saying which field is wrong.

    Raises ``BadEntryError`` for a line aimed at the wrong kind of widget and
    ``ValueError`` — pydantic's own, which already says which field and why —
    for one that is the right shape and still not valid, an end before its start
    being the case that happens.
    """
    shown = kept(item)
    return _for_list(data) if isinstance(shown, ListPayload) else _for_countdown(data)


async def _write(item: ItemRead, shown: Kept, entries: list[Entry]) -> ItemRead:
    """Put these entries in place of the old ones, and tell every board."""
    return await service.update(
        item, ItemUpdate(payload=shown.model_copy(update={"items": entries}))
    )


async def append(item: ItemRead, data: EntryCreate) -> tuple[ItemRead, int]:
    """Add one entry to the end of what this widget keeps, and say how many it now holds.

    Appending is the whole point: the caller does not need to know what is
    already there, and nothing anybody else put there is lost.
    """
    shown = kept(item)
    entries: list[Entry] = [*shown.items, built(item, data)]
    return await _write(item, shown, entries), len(entries)


async def drop(item: ItemRead, title: str) -> tuple[ItemRead, int]:
    """Take one entry out, naming the line as it is written on the screen.

    Matched on the text itself, ignoring case and the space around it: you are
    removing something readable from the sofa, not an index nobody there can
    count. The first line that reads that way goes and the rest are left alone.
    """
    shown = kept(item)
    entries: list[Entry] = list(shown.items)
    wanted = title.strip().casefold()
    found = next(
        (i for i, entry in enumerate(entries) if title_of(entry).strip().casefold() == wanted),
        None,
    )
    if found is None:
        raise NoEntryError(item, title, [title_of(e) for e in entries])
    del entries[found]
    return await _write(item, shown, entries), len(entries)
