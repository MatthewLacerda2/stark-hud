"""What counts as a colour anywhere on the board."""

import re
from typing import Annotated

from pydantic import AfterValidator

# What counts as a colour anywhere on the board. Hex in any of CSS's four
# lengths, a `var(--chart-2)` reaching for a theme token, a function like
# `rgb(...)` or `oklch(...)`, or a bare keyword such as `white`.
#
# The four-digit and eight-digit hex forms carry an alpha channel — `#rrggbbaa`
# — and that is the point of allowing them: a colour that is partly transparent
# is how text and chart marks are made to read over the video the board sits on,
# without a second field anywhere to say how solid they are.
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\Z")
_FUNCTION = re.compile(r"[a-zA-Z-]+\([^;]*\)\Z")
_KEYWORD = re.compile(r"[a-zA-Z]+\Z")


def _is_colour(value: str) -> str:
    """Refuse anything the browser would not read as a colour.

    A colour it cannot parse does not fail loudly: the declaration is dropped and
    the widget renders with no colour at all, which looks like the board losing
    the item rather than like a typo. Better to say so here, in a sentence.
    """
    text = value.strip()
    if not (_HEX.match(text) or _FUNCTION.match(text) or _KEYWORD.match(text)):
        raise ValueError(
            f"{value!r} is not a colour: pass hex (#rgb, #rrggbb, or #rrggbbaa "
            f"for one with alpha), a CSS function like rgb(...), or a name"
        )
    return text


Colour = Annotated[str, AfterValidator(_is_colour)]
