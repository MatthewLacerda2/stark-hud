"""The board on disk: one ``.hud`` file, written whole.

JSON in a file rather than a database because the board is a few dozen objects
that are always read together and never queried: anything with tables would be
machinery around a single ``read the whole thing`` and a single ``write the
whole thing``. The extension is ours so a file manager can hand it back to us,
but the bytes are plain JSON on purpose — the file is meant to be opened,
edited, copied and swapped by hand.

Writes are whole-file and atomic (temp file, then rename), so a power cut leaves
either the previous board or the new one, never half of each. Nothing here knows
what a board *is*; ``services.persistence`` decides what goes in.
"""

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

from core.config import get_settings
from schemas.board import Background, Ink, ItemRead
from schemas.notifications import Notification

logger = logging.getLogger(__name__)

# Bumped when the shape changes in a way an older file cannot satisfy. A file
# from the future is refused rather than half-read.
#
# 2 took pages out. A format-1 board loads: `page` is an extra key on an item
# and ignored, so every widget lands on the one board there is now. That can
# leave two of them overlapping, which nothing on the board would otherwise
# allow — so it is said out loud in the log rather than left to be noticed from
# the sofa. Groups replaced pages and are ordinary widgets, so they need nothing
# here.
FORMAT = 2

_dirty = False


class HudFile(BaseModel):
    """What a ``.hud`` file holds.

    Notifications live here too: they are as much the state of the screen as the
    widgets are, and losing them on every restart was the one thing about this
    board that behaved like a toy.
    """

    hud: int = FORMAT
    saved_at: datetime | None = None
    items: list[ItemRead] = []
    background: Background | None = None
    ink: Ink | None = None
    notifications: list[Notification] = []


def path() -> Path | None:
    """Where the board is kept, or ``None`` when persistence is switched off."""
    configured = get_settings().STATE_FILE.strip()
    return Path(configured) if configured else None


def touch() -> None:
    """Mark the board as changed since the last write."""
    global _dirty  # noqa: PLW0603 - module-level flag, same as the stores
    _dirty = True


def dirty() -> bool:
    """Whether anything has changed since the last successful write."""
    return _dirty


def write(state: HudFile) -> bool:
    """Write the board out atomically. Returns whether it went to disk."""
    global _dirty  # noqa: PLW0603 - module-level flag, same as the stores
    target = path()
    if target is None:
        return False

    state.saved_at = datetime.now(UTC)
    body = state.model_dump_json(indent=2)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Same directory as the target: rename is only atomic within a filesystem.
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".hud-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        logger.exception("could not write %s", target)
        return False

    _dirty = False
    return True


def _salvage(document: dict) -> HudFile:
    """Build a board from a file, skipping the parts this build cannot read.

    Items are validated one at a time on purpose. The file is a schema written
    down, and a schema changes: a widget kind that has lost a field, or gained a
    required one, must cost that widget and nothing else. Refusing the whole
    document takes the background, the clock and every notification with it —
    which is exactly what happened the first time a field was removed.
    """
    turned = sum(1 for entry in document.get("items") or [] if (entry or {}).get("page"))
    if turned:
        logger.warning(
            "%s widgets were on a page other than the first; pages are gone and they are "
            "all on the one board now, possibly overlapping",
            turned,
        )

    kept: list[ItemRead] = []
    for entry in document.get("items") or []:
        try:
            kept.append(ItemRead.model_validate(entry))
        except ValidationError:
            kind = (entry or {}).get("payload", {}).get("kind", "?")
            logger.warning("dropping a %s widget this build cannot read", kind)

    notes: list[Notification] = []
    for entry in document.get("notifications") or []:
        try:
            notes.append(Notification.model_validate(entry))
        except ValidationError:
            logger.warning("dropping a notification this build cannot read")

    background = None
    if document.get("background"):
        try:
            background = Background.model_validate(document["background"])
        except ValidationError:
            logger.warning("dropping a background this build cannot read")

    # A board written before the ink was settable simply has none, which is the
    # same thing as asking for the default. No migration, and nothing to bump.
    ink = None
    if document.get("ink"):
        try:
            ink = Ink.model_validate(document["ink"])
        except ValidationError:
            logger.warning("dropping an ink this build cannot read")

    return HudFile(
        hud=document.get("hud", FORMAT),
        items=kept,
        notifications=notes,
        background=background,
        ink=ink,
    )


def read() -> HudFile | None:
    """Read the board back, or ``None`` when there is nothing usable to read.

    A file that will not parse is moved aside rather than deleted or written
    over: it is likely something a human was editing, and their mistake should
    still be there for them to fix.
    """
    source = path()
    if source is None or not source.exists():
        return None

    try:
        raw = source.read_text(encoding="utf-8")
    except OSError:
        # Unreadable is not the same as unusable: a permission or device error
        # says nothing about the contents, and moving a perfectly good board
        # aside over one would destroy exactly what this file exists to keep.
        logger.exception("could not read %s; starting empty and leaving it alone", source)
        return None

    try:
        document = json.loads(raw)
        if not isinstance(document, dict):
            raise ValueError("a board is an object")
    except (ValueError, UnicodeDecodeError):
        spoiled = source.with_suffix(source.suffix + ".bad")
        logger.exception("%s is not a readable board; moved to %s", source, spoiled)
        source.replace(spoiled)
        return None

    state = _salvage(document)

    if state.hud > FORMAT:
        logger.error("%s is format %s, this build reads %s", source, state.hud, FORMAT)
        return None
    return state
