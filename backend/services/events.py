"""What the television is told, and the only place it is told anything.

A board that has changed and not said so is the worst thing this project can
produce: the TV goes on showing the old widget, nobody is standing at it, and it
looks perfectly fine. Nothing catches that. So announcing is not left to whoever
happens to be writing — it is part of the write.

Two rules make that hold:

1. **``core.hub`` is imported here and nowhere else in the stack.** A surface
   cannot broadcast because a surface cannot reach the hub; ``lint/house_lint``
   fails the build on an import that tries. Event names are constants in this
   file rather than string literals at thirty call sites, so a typo is a
   ``NameError`` at import and not a widget that never updates.
2. **The service that makes the change calls the function here.** A handler and
   a tool both end up in the same service, so neither of them can forget and
   only one of them has to remember. That is also why so many services in this
   package are ``async`` with nothing to await but this: the announcement is the
   awaited thing.

Everything here takes models and does its own ``model_dump``, because the shape
on the wire is what ``frontend/src/hooks/use-board.ts`` reduces and it should be
decided in one place too.
"""

from typing import Any

from core.hub import hub
from repositories import board as repo
from schemas.board import Background, BoardArranged, Ink, ItemRead
from schemas.notifications import Notification
from schemas.speech import Spoken
from services import origin

# The vocabulary. A name that appears here appears nowhere else in the backend.
ITEM_CREATED = "item.created"
ITEM_ORIGIN = "item.origin"
ITEM_UPDATED = "item.updated"
ITEM_REMOVED = "item.removed"
ITEM_WAKING = "item.waking"
BOARD_ARRANGED = "board.arranged"
BOARD_CLEARED = "board.cleared"
BACKGROUND_CHANGED = "background.changed"
INK_CHANGED = "ink.changed"
MESH_RELOADED = "mesh.reloaded"
NOTIFICATION_CREATED = "notification.created"
NOTIFICATION_REMOVED = "notification.removed"
NOTIFICATIONS_CLEARED = "notifications.cleared"
SPEECH_SPOKEN = "speech.spoken"


async def _send(event: str, data: Any) -> None:
    """Put one event on every socket looking at this board."""
    await hub.broadcast(event, data)


async def created(item: ItemRead) -> None:
    """A new widget, and — when there is one to say — what made it.

    The only way a creation reaches the socket, which is what keeps the origin
    attached to it: the two used to be sent together in ``services.origin`` for
    exactly this reason, and moving the pair here changes nothing about that
    except who owns the hub.
    """
    await _send(ITEM_CREATED, item.model_dump(mode="json"))
    text = origin.spoken()
    if text is not None:
        await _send(ITEM_ORIGIN, {"id": item.id, "text": text})


async def updated(item: ItemRead) -> None:
    """One widget, rewritten. The commonest event on this board by far."""
    await _send(ITEM_UPDATED, item.model_dump(mode="json"))


async def removed(item_id: str) -> None:
    """One widget, gone."""
    await _send(ITEM_REMOVED, {"id": item_id})


async def arranged(items: list[ItemRead] | None = None) -> None:
    """The whole board and the page it is turned to, as one change.

    Sent by everything that moves several widgets at once: a rearrangement, a
    fold, a regrouping, a page turn, disbanding a group. Ten ``item.updated``
    would render ten times and the change would crawl across the television a
    widget at a time.

    The board is read back from the repository unless the caller has it in hand,
    so a caller cannot send a stale one by forgetting to re-read.
    """
    board = items if items is not None else repo.list_items()
    whole = BoardArranged(items=board, showing=repo.showing())
    await _send(BOARD_ARRANGED, whole.model_dump(mode="json"))


async def cleared(removed_count: int) -> None:
    """Every widget on every page taken off at once."""
    await _send(BOARD_CLEARED, {"removed": removed_count})


async def background_changed(background: Background | None) -> None:
    """The video behind the grid, or ``None`` for the plain dark ground."""
    await _send(BACKGROUND_CHANGED, background.model_dump(mode="json") if background else None)


async def ink_changed(ink: Ink | None) -> None:
    """The colour the board writes in, or ``None`` for the stylesheet's."""
    await _send(INK_CHANGED, ink.model_dump(mode="json") if ink else None)


async def waking(item_id: str) -> None:
    """This widget is about to be written to, said before the writing starts.

    Not board state, which is why it is not an update: the whole value is in
    arriving earlier than the write does, and a page that connects afterwards
    has rightly missed it.
    """
    await _send(ITEM_WAKING, {"id": item_id})


async def mesh_reloaded(item_id: str) -> None:
    """A mesh's file changed under it, so whoever is drawing it should re-read.

    Not board state either: nothing about the widget moved, and an
    ``item.updated`` would rewrite ``board.hud`` and redraw an identical payload
    on every other client.
    """
    await _send(MESH_RELOADED, {"id": item_id})


async def notified(notification: Notification) -> None:
    """One line into the inbox."""
    await _send(NOTIFICATION_CREATED, notification.model_dump(mode="json"))


async def dismissed(notification_id: str) -> None:
    """One line out of the inbox."""
    await _send(NOTIFICATION_REMOVED, {"id": notification_id})


async def inbox_cleared(removed_count: int) -> None:
    """The whole inbox emptied at once."""
    await _send(NOTIFICATIONS_CLEARED, {"removed": removed_count})


async def spoken(line: Spoken) -> None:
    """A line the board should say out loud. The page does the speaking."""
    await _send(SPEECH_SPOKEN, line.model_dump(mode="json"))
