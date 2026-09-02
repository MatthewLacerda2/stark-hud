"""What counts as an icon anywhere on the board."""

from typing import Annotated

from pydantic import AfterValidator

from schemas import svg
from schemas.notifications import ICONS

UNKNOWN = (
    "is not an icon: pass one of {names}, an absolute path to an image file, "
    "or SVG markup starting with <svg>"
)


def _is_icon(value: str) -> str:
    """Refuse an icon that is none of the three things an icon may be.

    A name from the set, a path to a picture on this machine, or SVG markup —
    which is how a session draws something the vocabulary has no name for,
    without waiting for anyone to vendor an icon into the codebase.

    Markup is the one form that changes on the way through: what comes back is
    the sanitised version, and that is what gets stored. Anything else would let
    whatever is on the LAN run JavaScript on the television.

    Refused rather than quietly dropped, so a typo is visible to whoever wrote
    it. Whether the file is still there is a separate question, answered when
    the picture is asked for.
    """
    if svg.looks_like_svg(value):
        return svg.sanitise(value)
    if value not in ICONS and not value.startswith("/"):
        raise ValueError(f"{value!r} " + UNKNOWN.format(names=", ".join(sorted(ICONS))))
    return value


# Written like `Colour`, and for the same reason: a field says what it holds and
# the check comes with it, instead of every model repeating a validator.
Icon = Annotated[str, AfterValidator(_is_icon)]
