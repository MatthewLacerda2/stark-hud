"""What counts as a colour anywhere on the board."""

import re
from typing import Annotated

from pydantic import AfterValidator

# The board's palette, mirroring `--color-*` in `frontend/src/styles.css`.
#
# Passing one of these names is the same as passing `var(--color-<name>)`, and it
# is how a session reaches for the board's own colours without knowing what they
# are: `accent` follows the theme wherever the theme goes, `#d97757` does not.
#
# The set is closed, and it is checked rather than trusted — `test_colour.py`
# reads the stylesheet and fails when the two drift. A name accepted here and
# missing there resolves to a variable nothing defines, which the browser drops
# in silence: the widget renders with no colour and nothing anywhere says why.
TOKENS = frozenset(
    {
        "background",
        "foreground",
        "card",
        "card-foreground",
        "popover",
        "popover-foreground",
        "primary",
        "primary-foreground",
        "secondary",
        "secondary-foreground",
        "muted",
        "muted-foreground",
        "accent",
        "accent-foreground",
        "destructive",
        "destructive-foreground",
        "border",
        "input",
        "ring",
        "success",
        "success-foreground",
        "warning",
        "warning-foreground",
        "info",
        "info-foreground",
        "chart-1",
        "chart-2",
        "chart-3",
        "chart-4",
        "chart-5",
        "chart-6",
    }
)

# Bare words that are not tokens, and deliberately few.
#
# The rule here used to be "any word", which is how a misspelt token got through:
# `acent` is a perfectly good word, so it validated, reached the browser as a
# colour no browser knows, and was dropped without a sound. Every other CSS
# colour name has a hex spelling, so the cost of this list being short is one
# lookup, and the gain is that a wrong name is a sentence rather than a widget
# that quietly lost its colour.
_KEYWORDS = frozenset({"transparent", "currentcolor", "inherit", "white", "black"})

# Hex in any of CSS's four lengths. The four- and eight-digit forms carry an
# alpha channel — `#rrggbbaa` — and that is the point of allowing them: a colour
# that is partly transparent is how text and chart marks are made to read over
# the video the board sits on, with no second field to say how solid they are.
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\Z")
_FUNCTION = re.compile(r"[a-zA-Z-]+\([^;]*\)\Z")
_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9-]*\Z")


def _is_colour(value: str) -> str:
    """Resolve a token name, or refuse anything the browser would not read.

    A colour the browser cannot parse does not fail loudly: the declaration is
    dropped and the widget renders with no colour at all, which looks like the
    board losing the item rather than like a typo. Better to say so here, in a
    sentence naming what would have worked.
    """
    text = value.strip()
    if text in TOKENS:
        return f"var(--color-{text})"
    if _HEX.match(text) or _FUNCTION.match(text):
        return text
    if _WORD.match(text) and text.lower() in _KEYWORDS:
        return text
    raise ValueError(
        f"{value!r} is not a colour: pass one of the board's own "
        f"({', '.join(sorted(TOKENS))}), hex (#rgb, #rrggbb, or #rrggbbaa for "
        f"one with alpha), a CSS function like rgb(...), or {', '.join(sorted(_KEYWORDS))}"
    )


Colour = Annotated[str, AfterValidator(_is_colour)]
