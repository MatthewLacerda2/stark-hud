"""What a music file says about itself, read where the file actually is.

The queue holds paths, and a path is not a name. `07. Back In Black.mp3` is the
whole of what a filename knows: nothing in it says who is playing or what record
it came off. Both are in the file's own tags, so both are read from the file.

Here rather than in the browser, because the browser cannot see the disk — a
track is streamed by the widget's id and its place in the queue, and the path
never leaves this machine. So the tags are read once, when the queue is built,
and travel with the track in the payload every viewer already receives.

`mutagen` does the reading. It is pure Python with no system libraries behind
it, and it puts ID3 frames, Vorbis comments and MP4 atoms behind one dictionary,
so nothing here grows a branch per container.
"""

from collections.abc import Mapping
from typing import Any, NamedTuple

import mutagen


class Tags(NamedTuple):
    """What a file says it is. Any of it may be missing, and often one is."""

    title: str | None = None
    artist: str | None = None
    album: str | None = None


def _first(tags: Mapping[str, Any], *names: str) -> str | None:
    """The first non-empty value under any of those names, or nothing.

    Tags are lists because a track may credit two artists, and a tag that is
    present but blank is what a ripper leaves when it had nothing to put there —
    both come back here as nothing rather than as an empty string, so the widget
    is never asked to draw a label with air beside it.
    """
    for name in names:
        for value in tags.get(name) or []:
            text = str(value).strip()
            if text:
                return text
    return None


def read(path: str) -> Tags:
    """The title, artist and album a file carries, as far as it carries them.

    Nothing here is an error. A file with no tags, a file that is not really
    audio, and a file that is not there yet all come back empty, and the widget
    then shows what it can — which is the name the filename gives it, never the
    word "Unknown" and never a row of labels with nothing beside them.
    """
    try:
        found = mutagen.File(path, easy=True)
    except (mutagen.MutagenError, OSError, ValueError):
        return Tags()
    if found is None or found.tags is None:
        return Tags()
    return Tags(
        title=_first(found.tags, "title"),
        # A compilation names the track's artist and the record's separately.
        # Whoever is playing this track is the truer answer of the two, and the
        # album's artist is what to say when the track does not name one.
        artist=_first(found.tags, "artist", "albumartist"),
        album=_first(found.tags, "album"),
    )
