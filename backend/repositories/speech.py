"""The lines the board has said. The only module that touches them.

Two halves that have to agree: the records, in memory and mirrored to the
``.hud`` file beside the widgets and the notifications, and the audio, one MP3
per line in a directory the backend owns. They are kept together and pruned
together, so a line that can be listed can be played, and the directory never
grows past the newest ``SPEECH_KEEP``.
"""

import re
from pathlib import Path

from core.config import get_settings
from repositories import store
from schemas.speech import Spoken

# An id is a uuid and nothing else. It arrives in a URL and is turned into a
# filename, so it is checked rather than trusted: `../../board.hud` is a path,
# not a line the board once said.
_ID = re.compile(r"[0-9a-f]{32}")

# Oldest first, the order they were said in.
_lines: list[Spoken] = []


def folder() -> Path:
    """The directory the audio lives in, made if it is not there yet."""
    path = Path(get_settings().SPEECH_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _prune(keep: int) -> None:
    """Keep the newest few, record and audio alike, and nothing else.

    Every MP3 in the directory that no kept record names goes, not just the one
    that fell off the end. The directory is ours, and anything else in it is a
    line nobody can list any more: one left behind by a crash between writing
    the audio and the record, or by the voice that came before this one.
    """
    del _lines[:-keep]
    kept = {line.id for line in _lines}
    for audio in folder().glob("*.mp3"):
        if audio.stem not in kept:
            audio.unlink(missing_ok=True)


def add(line: Spoken, audio: bytes) -> None:
    """Keep one line, its audio first so a listed line is always playable."""
    (folder() / f"{line.id}.mp3").write_bytes(audio)
    _lines.append(line)
    _prune(get_settings().SPEECH_KEEP)
    store.touch()


def list_all() -> list[Spoken]:
    """Every line still kept, newest first."""
    return list(reversed(_lines))


def get(speech_id: str) -> Spoken | None:
    """One line by id, or ``None``."""
    return next((line for line in _lines if line.id == speech_id), None)


def find_audio(speech_id: str) -> Path | None:
    """The MP3 for a line, or nothing when it was never said or has aged out."""
    if not _ID.fullmatch(speech_id):
        return None
    target = folder() / f"{speech_id}.mp3"
    return target if target.is_file() else None


def load(lines: list[Spoken]) -> None:
    """Replace everything with what came off disk, oldest first."""
    _lines[:] = sorted(lines, key=lambda line: line.created_at)


def clear() -> None:
    """Forget every record. The audio stays: it is pruned by the next line."""
    _lines.clear()
