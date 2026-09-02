"""What counts as an icon anywhere on the board."""

from typing import Annotated

from pydantic import AfterValidator

from schemas.notifications import ICONS


def _is_icon(value: str) -> str:
    """Refuse an icon that is neither a name from the set nor a path to a picture.

    The vocabulary a notification's icon has, because an icon is an icon: any
    widget may point at a file on this machine instead of picking a glyph.
    Refused rather than quietly dropped, so a typo is visible to whoever wrote
    it. Whether the file is still there is a separate question, answered when
    the picture is asked for.
    """
    if value not in ICONS and not value.startswith("/"):
        raise ValueError(
            f"{value!r} is not an icon: pass one of {', '.join(sorted(ICONS))}, "
            "or an absolute path to an image file"
        )
    return value


# Written like `Colour`, and for the same reason: a field says what it holds and
# the check comes with it, instead of every model repeating a validator.
Icon = Annotated[str, AfterValidator(_is_icon)]
