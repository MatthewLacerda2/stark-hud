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
from schemas.board import DEFAULT_PAGE, Background, Ink, ItemRead
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
#
# 3 gave a group three states, so `open: true` became `state: "open"`. A
# format-2 board is not migrated and does not need to be: a payload refuses keys
# it does not know, so every group in it fails validation, and `_salvage` drops
# those widgets with a warning each and keeps the rest of the file. What that
# costs is the groups themselves and nothing else — their members come back
# loose on the board, possibly overlapping. Almost everything here rebuilds
# itself: `tools/agent.py` rewrites the panels it feeds, positions included,
# within a tick of coming up, and a screen worth having is worth saying again.
# What is not acceptable is a board that will not start, which is why this is a
# drop and not a refusal.
#
# 4 put pages back, and this time they are what they should have been. A page is
# a name a widget carries and the board shows one of them; the file gained
# `page` on every item and `showing` beside `items`. A format-3 board needs no
# migration at all — both default, so every widget lands on the one page there
# was and the board comes up turned to it, which is exactly what a board with no
# pages in it meant. What does not survive is a group in the state `away`, which
# was a group doing a page's job: `state` is now a two-value literal, so such a
# group fails validation and `_salvage` drops it with a warning, leaving its
# widgets loose on the page. That costs the screens and nothing else, and no
# board we have ever written to disk has had one.
FORMAT = 4

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
    # Which page the board was turned to. A file written before pages comes back
    # showing the page its widgets all defaulted onto, which is the whole of the
    # migration.
    showing: str = DEFAULT_PAGE
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


def _reattached(items: list[ItemRead]) -> list[ItemRead]:
    """The same widgets, with membership of a group that is no longer here dropped.

    A widget whose group this build could not read is loose on the board rather
    than gone with it, which is the rule the repository already keeps about
    losing a container. Left pointing at a group that is not there it would read,
    everywhere a session looks, as a widget that is somewhere it is not.
    """
    here = {i.id for i in items}
    return [i if i.parent_id in here else i.model_copy(update={"parent_id": None}) for i in items]


def _as_media(payload: dict) -> dict:
    """A stored ``video`` payload read as the one-track player it is now.

    This is the one place a widget kind is recognised after it has left the
    union, and it is here rather than anywhere upstream because a payload is
    validated on the way in: a ``video`` reaching ``ItemRead`` is a widget
    dropped, not a widget upgraded.

    A ``video`` was one local file with ``autoplay``, ``loop`` and ``muted``,
    which is a ``media`` with one track, ``playing``, ``loop`` and ``muted`` —
    and that is why the kind went. Every flag comes across, so a clip that was
    silent stays silent; what it gains is a transport, which a video never had.

    Nothing is bumped in ``FORMAT`` for this. That number is for a file an older
    build cannot read, and ``media`` predates the fold: a board written today
    loads on the build before this one.
    """
    return {
        "kind": "media",
        "tracks": [{"path": payload.get("path")}],
        "playing": payload.get("autoplay", True),
        "loop": payload.get("loop", False),
        "muted": payload.get("muted", True),
    }


def _one_page(entry: dict) -> dict:
    """The same widget with a page name on it, whatever the file called a page.

    Format 1 numbered its pages, and a number is not a name: left alone it would
    fail validation and cost the widget, which is the one thing a restore is not
    allowed to do. The numbers are not kept — format 2 already decided that an
    old file comes up as one board — so they all land on the default page,
    possibly overlapping, the same as they did before this key meant anything.
    """
    if isinstance(entry.get("page"), str):
        return entry
    if entry.get("page") is not None:
        logger.warning(
            "widget was on numbered page %s; it is on %s now", entry["page"], DEFAULT_PAGE
        )
    return {**entry, "page": DEFAULT_PAGE}


def _salvage(document: dict) -> HudFile:
    """Build a board from a file, skipping the parts this build cannot read.

    Items are validated one at a time on purpose. The file is a schema written
    down, and a schema changes: a widget kind that has lost a field, or gained a
    required one, must cost that widget and nothing else. Refusing the whole
    document takes the background, the clock and every notification with it —
    which is exactly what happened the first time a field was removed.
    """
    kept: list[ItemRead] = []
    upgraded = 0
    for entry in document.get("items") or []:
        entry = _one_page(entry or {})
        if (entry.get("payload") or {}).get("kind") == "video":
            entry = {**entry, "payload": _as_media(entry["payload"])}
            upgraded += 1
        try:
            kept.append(ItemRead.model_validate(entry))
        except ValidationError:
            kind = entry.get("payload", {}).get("kind", "?")
            logger.warning("dropping a %s widget this build cannot read", kind)

    # Read is also written: the board is saved whole, so marking it changed puts
    # the upgraded widgets back on disk at the next flush, and the day no file
    # has a video in it is the day `_as_media` can go. Nothing else about a
    # restore is dirty — what was just read is what is already there — but this
    # genuinely is: the board now differs from the file it came from.
    if upgraded:
        logger.info("read %s video widgets as players with one track", upgraded)
        touch()

    kept = _reattached(kept)

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
        showing=document.get("showing") or DEFAULT_PAGE,
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
    except ValueError, UnicodeDecodeError:
        spoiled = source.with_suffix(source.suffix + ".bad")
        logger.exception("%s is not a readable board; moved to %s", source, spoiled)
        source.replace(spoiled)
        return None

    state = _salvage(document)

    if state.hud > FORMAT:
        logger.error("%s is format %s, this build reads %s", source, state.hud, FORMAT)
        return None
    return state
