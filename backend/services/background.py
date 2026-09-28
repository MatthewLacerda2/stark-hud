"""The video behind the grid, and the board-ready copy it is played from.

A background is set by naming a file that stays wherever its owner keeps it.
What the page plays, once it can, is a copy made from it here: a quarter of the
pixels at four fifths of the frames, and otherwise the same video.

Why a copy at all. The browser decodes h264 in software on this machine, so a
background costs pixels times frames, whatever is done with them afterwards; and
a blurred background throws almost all of its pixels away. A 1080p30 loop behind
a nine-pixel blur was half a core spent on detail the blur then erased (#142).

The blur itself stays in the browser. It costs a point or two of a core, and it
is the only blur that is nine pixels on every screen the tab is ever shown on:
baked into the copy it would be nine pixels on one screen width and wrong on the
rest — measured, it was visibly sharper even on the width it was worked out for.
The copy only takes away pixels the browser's blur was going to erase anyway.

Four rules keep it from being a thing anybody has to think about:

1. **Once per background, never per play.** A copy is named after what it was
   made from — the path, the file's size and modification time, and the recipe
   below — so asking again for a copy that exists makes nothing, and a file
   replaced in place, or a change to the recipe, makes a new one.
2. **The board never waits for it.** Setting a background answers at once and
   the page plays the original. When the copy is ready the page is told again
   and switches over, where the loop had got to.
3. **Nothing regresses without ffmpeg.** No ffmpeg, a failed encode, or
   ``BACKGROUND_DIR`` left empty all mean the same thing: no copy, and the
   original keeps playing exactly as it did before copies existed.
4. **Only the copy of the current background is kept.** It is derived, a few
   megabytes, and remade in seconds if it is ever needed again, so the directory
   holds one file rather than a history.

A sharp background gets no copy. It is sharp because the video is the point,
and every pixel a smaller copy drops is one somebody is looking at.
"""

import asyncio
import hashlib
import logging
import shutil
from pathlib import Path

from core.config import get_settings
from core.refusal import BoardRefusal
from repositories import board as repo
from schemas.board import Background, BackgroundRead
from services import events

logger = logging.getLogger(__name__)

# The copy, as ffmpeg is asked for it. Both numbers were measured against the
# original in a browser on this machine — see the pull request for #142.
#
# 960x540: a nine-pixel blur leaves almost nothing finer than twenty screen
# pixels, and a 540p copy on a 1080p screen still holds detail down to four. The
# scale covers rather than fits, so a video of any shape fills the screen the
# way `object-cover` fills it. Screenshots of the same frame, original and copy,
# blurred by the page, could not be told apart at 1920 or at 2560 wide.
#
# 24 fps, or the original's own rate if that is slower: a fifth fewer frames to
# decode, in a loop whose motion the blur has already softened.
_FILTERS = (
    "fps=fps='min(24,source_fps)',"
    "scale=960:540:force_original_aspect_ratio=increase:force_divisible_by=2"
)
# Part of every copy's name, so changing either number above is a new copy for
# every background rather than an old one quietly kept.
RECIPE = "540p24"


class MissingFileError(BoardRefusal):
    """Raised when a background points at a path that is not a file."""

    status = 404

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"No file at {path}")


# Copies being made right now, by name. Held so a second request for the same
# copy waits on the first instead of starting another, and so the task is not
# collected half way through: the event loop keeps only a weak reference.
_making: dict[str, asyncio.Task[None]] = {}


async def set_background(background: Background | None) -> BackgroundRead | None:
    """Set or clear the video background, checking the file exists first.

    Items with a missing file show a visible placeholder, so the problem
    announces itself. A missing background is just darkness, indistinguishable
    from having set none — so this one is checked up front.

    Answers with what the page is told: the copy, if there already is one, and
    otherwise the original while one is made.
    """
    if background is not None and not Path(background.path).is_file():
        raise MissingFileError(background.path)
    repo.set_background(background)
    await events.background_changed(shown())
    prepare()
    return shown()


def shown() -> BackgroundRead | None:
    """The current background, as the page is to play it."""
    background = repo.get_background()
    if background is None:
        return None
    return BackgroundRead(**background.model_dump(), board_copy=_ready(background))


def copy_path() -> Path | None:
    """The file the page plays in place of the original, when there is one."""
    background = repo.get_background()
    name = _ready(background) if background else None
    directory = _directory()
    return directory / name if name and directory else None


def prepare() -> None:
    """Start making the current background's copy, unless it exists or is under way.

    Called whenever a background is set, and once at startup, so a board that
    came back from disk — or was set before this existed — gets its copy too.
    """
    background = repo.get_background()
    name = _name(background) if background else None
    directory = _directory()
    if background is None or name is None or directory is None:
        return
    if (directory / name).is_file() or name in _making:
        return
    _making[name] = asyncio.create_task(_make(background, directory, name))


async def settled() -> None:
    """Wait for every copy under way to finish, one way or the other."""
    await asyncio.gather(*_making.values(), return_exceptions=True)


def abandon() -> None:
    """Stop every copy under way, on the way out. The next start makes it again."""
    for task in _making.values():
        task.cancel()


def _directory() -> Path | None:
    configured = get_settings().BACKGROUND_DIR
    return Path(configured) if configured else None


def _name(background: Background) -> str | None:
    """What this background's copy is called, or ``None`` if it gets none."""
    if not background.blur:
        return None
    try:
        stat = Path(background.path).stat()
    except OSError:
        return None
    made_from = f"{RECIPE}\n{background.path}\n{stat.st_size}\n{stat.st_mtime_ns}"
    return hashlib.sha256(made_from.encode()).hexdigest()[:16] + ".mp4"


def _ready(background: Background) -> str | None:
    """The copy's name if it has been made, and ``None`` while it has not."""
    name = _name(background)
    directory = _directory()
    return name if name and directory and (directory / name).is_file() else None


async def _make(background: Background, directory: Path, name: str) -> None:
    """Make one copy, keep it, and tell the page if it is still the one showing."""
    target = directory / name
    partial = target.with_suffix(".part")
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if not await encode(Path(background.path), partial):
            partial.unlink(missing_ok=True)
            return
        partial.replace(target)
    except OSError as exc:
        # A directory it cannot write is the same as no ffmpeg: no copy, and
        # the original goes on playing.
        logger.warning("could not keep a copy of the background in %s: %s", directory, exc)
        return
    finally:
        del _making[name]
    # Another background may have been set while this one was being made, and
    # its copy may even have finished first. So what is kept is decided by what
    # is showing now, not by which encode happened to end last.
    current = repo.get_background()
    _keep_only(directory, _name(current) if current else None)
    if current == background:
        await events.background_changed(shown())


async def encode(source: Path, target: Path) -> bool:
    """Run ffmpeg once, into ``target``. Whether it made a copy is the answer.

    At the lowest priority there is, because nothing is waiting on it: the page
    is already playing the original. Video only — the background never plays
    sound, so the copy carries none.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        logger.warning("no ffmpeg here, so the background plays as it is: %s", source)
        return False
    # fmt: off
    argv = [
        "nice", "-n", "19", ffmpeg, "-nostdin", "-v", "error", "-y",
        "-i", str(source), "-map", "0:v:0",
        "-vf", _FILTERS,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-f", "mp4", str(target),
    ]
    # fmt: on
    try:
        process = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
        )
    except OSError as exc:
        logger.warning("could not start ffmpeg for the background %s: %s", source, exc)
        return False
    try:
        _, errors = await process.communicate()
    except asyncio.CancelledError:
        process.kill()
        raise
    if process.returncode != 0:
        logger.warning("could not copy the background %s: %s", source, errors.decode()[-500:])
        return False
    return True


def _keep_only(directory: Path, keep: str | None) -> None:
    """Delete every finished copy but the current background's."""
    for old in directory.glob("*.mp4"):
        if old.name != keep:
            old.unlink(missing_ok=True)
