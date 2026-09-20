"""What comes back when a browser hands this board a file.

A path, because a path is what a media queue holds. That is the whole design:
the endpoint turns bytes that have no name on this machine into a file that has
one, and hands back the name. What happens next — `set_media_queue`, or the
button #114 will put on the widget — is the call that was always there, given a
path like any other.

So the media widget never learns that a track was uploaded, and nothing in
`schemas.media` changes. A track is a file on this machine; these are files on
this machine. The only thing that knows the difference is `services.uploads`,
which knows because it is the one allowed to delete them.

Its own module rather than a model in `schemas.media`, which is at 300 of its
350 lines: receiving a file and playing one are different halves of the day, and
the seam is already there.
"""

from pydantic import BaseModel, ConfigDict


class Uploaded(BaseModel):
    """One file now on the host's disk, in the words a queue understands."""

    model_config = ConfigDict(extra="forbid")

    # Where it went. This is the value to put in a media queue, and it is a path
    # on the machine the backend runs on — never a URL, because a filesystem
    # path never appears in one on this board. A track is fetched by the
    # widget's id and its place in the queue, the same as every other local file.
    path: str
    # What the file ended up being called, which is not quite what the browser
    # said: see `services.uploads.stored_name`. Handed back so a caller can show
    # the name the board will show, rather than the one it sent.
    name: str
    # How much arrived. The caller already knows how big the file was, which is
    # exactly why this is worth returning: it is the one number that says the
    # upload finished rather than stopped.
    bytes: int
