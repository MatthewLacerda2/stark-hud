"""What a browser hands this board to play: a file, and then the track it became.

A path comes back, because a path is what a media queue holds. That is the whole
design: the endpoint turns bytes that have no name on this machine into a file
that has one, and hands back the name. What happens next — `set_media_queue`, or
the button on the widget — is a queue built from that path like any other.

The button does not write the queue with a plain PATCH, and `HandedTrack` is
why. A queue built by a PATCH carries whatever the page sent, and the page cannot
read tags or stamp a file: two uploads in a row would both be track 0 with no
stamp, the same URL over different bytes, and the browser would go on playing
the first. So the button hands over one track and the server builds it, the way
`set_media_queue` does.

So the media widget never learns that a track was uploaded, and nothing in
`schemas.media` changes. A track is a file on this machine; these are files on
this machine. The only thing that knows the difference is `services.uploads`,
which knows because it is the one allowed to delete them.

Its own module rather than a model in `schemas.media`, which is at 300 of its
350 lines: receiving a file and playing one are different halves of the day, and
the seam is already there.
"""

from pydantic import BaseModel, ConfigDict, model_validator


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


class HandedTrack(BaseModel):
    """One track a person puts on a player by hand, in place of what it held.

    Either the path an upload came back with, or a YouTube link exactly as it was
    pasted. Two fields rather than one string, because the box somebody pastes
    into is a YouTube box: a link to anywhere else has to be refused as "not
    YouTube", not taken for a file on this machine that happens to be named
    ``https://…`` — which is what a single string would turn it into.
    """

    model_config = ConfigDict(extra="forbid")

    path: str | None = None
    youtube: str | None = None

    @model_validator(mode="after")
    def _one(self) -> HandedTrack:
        """Refuse a body that names both, or neither."""
        if (self.path is None) == (self.youtube is None):
            raise ValueError("hand over a path or a youtube link, and not both")
        return self
