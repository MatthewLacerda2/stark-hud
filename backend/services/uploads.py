"""Taking a file from a browser, and deleting it once nothing plays it.

A media widget plays a path on this machine. That works when a session on the
host names the file, and not at all for a person with a browser: a file picker
hands the page the file's *contents*, and the browser is usually not even the
machine the board runs on. So the bytes have to arrive, land somewhere, and
become a path — after which nothing else about the widget changes.

Three things this module is careful about, each for a measured reason.

**It never holds the file.** A film is gigabytes and this is a LAN, so the bytes
are written to their final home a chunk at a time, straight off the request. The
route hands us the stream rather than a parsed form for the same reason: a
multipart parser spools the whole body to a temporary file before anything can
move it, which is the same bytes written twice on a machine with one disk.

**It never trusts the name.** What the browser sends is a string somebody could
have chosen, and it is about to be used as a filename. `stored_name` takes the
last segment and nothing else, so `../../etc/board.hud` is `board.hud`, and
strips what a filename must not carry. What it deliberately does *not* do is
reduce the name to ASCII: the file's stem becomes the track's title when it has
no tags, and that title is read across a room, so an accent survives and a
Japanese title survives. Isolation comes from the directory, not from the
alphabet.

**It deletes only from one directory.** Every upload gets a directory of its
own, named by a fresh uuid, and the file keeps its own name inside it. That is
what makes two uploads of `episode 1.mkv` two files rather than one file twice,
and it makes the sweep a question about directories rather than about names. A
path a session named elsewhere on this disk is never a candidate: the sweep
walks the upload directory and only ever unlinks what it finds there.
"""

from __future__ import annotations

import shutil
import unicodedata
import uuid
from collections.abc import AsyncIterator
from pathlib import Path, PurePosixPath
from time import time

from core.config import get_settings
from core.refusal import BoardRefusal
from repositories import board as repo
from schemas.board import MediaPayload
from schemas.media import MEDIA_TYPES
from schemas.uploads import Uploaded

# How long a name may be once it is on disk, in bytes rather than characters —
# the limit a filesystem enforces is on bytes, and a title in a script that is
# three bytes a character would otherwise pass this and fail the write. Well
# under the usual 255 so the suffix and a long extension always fit.
MAX_NAME_BYTES = 180

# What a file is called when the browser's name survives nothing: a name of only
# dots, or of only the characters taken out below. It is never the common case —
# the suffix has to have been playable to get this far — so it does not need to
# be pretty, only to be a name.
FALLBACK_STEM = "upload"


class UnplayableUpload(BoardRefusal):
    """Raised when the file is not one the board could play if it kept it.

    The allowlist is `MEDIA_TYPES`, which is the same table a queue is checked
    against — so a file refused here is a file that would have been refused the
    moment somebody tried to queue it, except that by then it would be on the
    disk. 415 rather than the queue's 422 because the question here really is
    the media type and nothing else.
    """

    status = 415

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"{name!r} is not an audio or video file this board can play. "
            f"It plays: {', '.join(sorted(MEDIA_TYPES))}."
        )


class EmptyUpload(BoardRefusal):
    """Raised when the request carried no bytes at all.

    Kept apart from the type refusal because it is a different accident: the
    name was fine and the transfer was not. A zero-byte file would queue
    perfectly and then fail to play, reporting a codec error about a file that
    is not a file, which is a true sentence about the wrong problem.
    """

    status = 422

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Nothing arrived for {name!r} — the upload was empty.")


def _root() -> Path:
    """The directory uploads live in, made if it is not there yet."""
    path = Path(get_settings().UPLOAD_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _legible(text: str) -> str:
    """The name with what a filename must not carry taken out of it.

    Path separators go because a name is not a path — both kinds, since a
    browser on Windows may say `\\`. Control characters go because a filename
    with a newline or a null byte in it is a filename that breaks whatever reads
    the directory next, and a null byte specifically is a `ValueError` out of
    every call that touches the disk. Whitespace is collapsed so a name of
    forty spaces is not a name of forty spaces.

    Everything else stays. The alternative — keeping an allowlist of letters —
    turns `Cidade de Deus.mkv` into dashes, and that stem is what the widget
    draws when the file has no tags to read.
    """
    kept = "".join(
        " " if unicodedata.category(ch) == "Cc" else ch for ch in text if ch not in "/\\"
    )
    return " ".join(kept.split())


def _trimmed(stem: str) -> str:
    """The stem, cut to something a filesystem will take, without splitting a character."""
    encoded = stem.encode()
    if len(encoded) <= MAX_NAME_BYTES:
        return stem
    return encoded[:MAX_NAME_BYTES].decode(errors="ignore").rstrip()


def stored_name(given: str) -> str:
    """What this file is called on disk, from whatever the browser said it was.

    The traversal defence is one line of it: `PurePosixPath(...).name` is the
    last segment, so `../../etc/board.hud` is `board.hud` and `/etc/passwd.mp4`
    is `passwd.mp4`, and neither can address anything but the directory this
    upload is about to get. Nothing here joins a path — the caller does that,
    with a name that is a name by then.

    The suffix decides whether the file is taken at all, before a byte is
    written: it is the same table a queue is checked against.
    """
    bare = PurePosixPath(given.replace("\\", "/")).name
    suffix = PurePosixPath(bare).suffix.lower()
    if suffix not in MEDIA_TYPES:
        raise UnplayableUpload(given)
    # Everything before the suffix, cleaned. A name that is nothing else — dots,
    # spaces, control characters — leaves an empty stem, and a file called
    # `.mp4` is a hidden file with no name, so it gets one.
    stem = _legible(bare[: -len(suffix)]).strip(" .") or FALLBACK_STEM
    return f"{_trimmed(stem)}{suffix}"


async def receive(name: str, chunks: AsyncIterator[bytes]) -> Uploaded:
    """Write a file arriving from a browser to disk, and say where it went.

    A chunk at a time into its final home. Nothing accumulates: peak memory is
    one chunk whether the file is a song or a four-hour film, which is the
    property the whole shape of this exists to have, and `tests/services/
    test_uploads.py` measures rather than asserts.

    The write is synchronous inside an async function on purpose. Each chunk is
    a handful of kilobytes into the page cache — microseconds — and the
    alternative, a thread hop per chunk, costs more in hops than it saves in
    blocking. What would be worth a thread is an `fsync`, and there is not one:
    a file lost to a power cut in the second after it arrived is a file the
    person can send again.

    A transfer that dies halfway leaves a partial file, because there is nothing
    the server can do about a browser that stopped. It is unreferenced by
    definition, so the sweep takes it.
    """
    filename = stored_name(name)
    folder = _root() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    target = folder / filename
    written = 0
    with target.open("wb") as sink:
        async for chunk in chunks:
            written += sink.write(chunk)
    if not written:
        shutil.rmtree(folder, ignore_errors=True)
        raise EmptyUpload(name)
    return Uploaded(path=str(target), name=filename, bytes=written)


def _queued() -> set[Path]:
    """Every local file any widget on the board currently names in a queue.

    Every page, not the one showing: a widget on page two is still a widget, and
    a board that deleted what was playing on another page would be worse than
    one that never deleted anything.
    """
    return {
        Path(track.path).resolve()
        for item in repo.list_items()
        if isinstance(item.payload, MediaPayload)
        for track in item.payload.tracks
        if track.path
    }


def _touched(entry: Path) -> float:
    """When anything inside this upload was last written.

    The newest file within, not the directory's own time. A directory's
    modification time is when its entries were created, which for an upload is
    the moment it *started* — so a film still arriving twenty minutes later
    would read as twenty minutes old and be swept out from under the socket
    writing it. The file's time moves while it is being written, and that is the
    one this has to ask.

    A stat that fails answers "now", which keeps the entry: the sweep's job is
    to reclaim disk, and it has no business guessing about something it cannot
    read.
    """
    try:
        times = [entry.stat().st_mtime]
        if entry.is_dir() and not entry.is_symlink():
            times += [child.stat().st_mtime for child in entry.rglob("*")]
    except OSError:
        return time()
    return max(times)


def sweep() -> list[str]:
    """Delete uploaded files no widget's queue still names. Returns what went.

    Called when a media widget is removed and when the board is cleared —
    the two moments a queue stops existing — and not on an ordinary write. A
    panel is rewritten every few seconds by the agent, and hanging a directory
    scan off every write would make the common case pay for the rare one.

    Two things are never deleted, and they are the whole of the safety here:

    * **Anything outside the upload directory.** This walks that directory and
      unlinks what it finds there. A path a session named — an album on a disk
      of albums — is not in it and cannot be reached from it.
    * **Anything younger than the grace window.** A file is on disk for a moment
      before anything refers to it, and in that moment it looks exactly like one
      whose widget has just gone. See `Settings.UPLOAD_GRACE_SECONDS`.
    """
    root = Path(get_settings().UPLOAD_DIR)
    if not root.is_dir():
        return []
    kept = _queued()
    cutoff = time() - get_settings().UPLOAD_GRACE_SECONDS
    gone: list[str] = []
    for entry in sorted(root.iterdir()):
        if _referenced(entry, kept) or _touched(entry) > cutoff:
            continue
        _delete(entry)
        gone.append(str(entry))
    return gone


def _referenced(entry: Path, kept: set[Path]) -> bool:
    """Whether any queue names this upload, or a file inside it."""
    here = entry.resolve()
    return any(path == here or here in path.parents for path in kept)


def _delete(entry: Path) -> None:
    """Remove one upload, whatever shape it turned out to be.

    A symlink is unlinked rather than followed: `rmtree` refuses one anyway, and
    following it would be this function reaching outside the only directory it
    is allowed to touch — which is the one thing it must never do, however it
    came to be pointed there.
    """
    if entry.is_symlink() or entry.is_file():
        entry.unlink(missing_ok=True)
    else:
        shutil.rmtree(entry, ignore_errors=True)
