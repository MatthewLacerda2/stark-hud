"""Keeping the board across restarts.

The board is small and always read whole, so there is nothing to be gained from
writing changes one at a time: the file is rewritten entire, and a change only
sets a flag. A loop writes it at most every ``STATE_FLUSH_SECONDS``, which turns
a chart refreshing every second into one write per window instead of one per
tick, and bounds what a power cut costs to that same window.

Restoring is deliberately forgiving. A board that will not load is a reason to
start empty and say so in the log, never a reason for the screen to stay black.
"""

import asyncio
import logging

from repositories import board as board_repo
from repositories import notifications as notifications_repo
from repositories import store
from repositories.store import HudFile
from schemas.board import ItemRead

logger = logging.getLogger(__name__)


def snapshot() -> HudFile:
    """Everything worth keeping, as it stands right now."""
    return HudFile(
        items=board_repo.list_items(),
        background=board_repo.get_background(),
        notifications=notifications_repo.list_all(),
    )


def save() -> bool:
    """Write the board out now. Returns whether it reached the disk."""
    return store.write(snapshot())


def _named_once(items: list[ItemRead]) -> list[ItemRead]:
    """Leave one widget holding each key, and take the name off the rest.

    A key names one widget, but that is enforced on the way in and a file on
    disk predates the rule — or was edited by hand, which this format invites.
    A second widget with the same key is unreachable rather than wrong: nothing
    can write to it, wake it or find it, and it sits on the television being fed
    by nobody. It keeps everything it is showing and loses only the name it
    could not answer to, which is the smaller loss of the two.
    """
    seen: set[str] = set()
    kept: list[ItemRead] = []
    for item in items:
        if item.key is not None and item.key in seen:
            logger.warning(
                "%s and another widget both claim the key %r; taking it off the later one",
                item.id,
                item.key,
            )
            item = item.model_copy(update={"key": None})
        elif item.key is not None:
            seen.add(item.key)
        kept.append(item)
    return kept


def restore() -> None:
    """Load the board from disk, if there is one to load."""
    state = store.read()
    if state is None:
        logger.info("starting with an empty board (%s)", store.path() or "persistence off")
        return

    board_repo.load(_named_once(state.items), state.background)
    notifications_repo.load(state.notifications)
    logger.info(
        "restored %s items and %s notifications from %s",
        len(state.items),
        len(state.notifications),
        store.path(),
    )


async def flusher(interval: float) -> None:
    """Write the board whenever it has changed, until cancelled."""
    while True:
        await asyncio.sleep(interval)
        if store.dirty():
            save()
