"""What survives the SVG sanitiser, and what does not.

This is the one place on the board where a caller's own markup ends up inside
the page the television is showing, and there is no authentication in front of
it. So the interesting cases are not the shapes that come through — they are the
things that must not.
"""

import pytest
from pydantic import ValidationError

from schemas.payloads import ListPayload
from schemas.svg import sanitise

# Shaped exactly like a lucide icon: its elements are the arrays lucide ships
# (`["path", {"d": ...}]`), painted with currentColor so the widget decides.
LUCIDE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 12v-2"/><rect x="2" y="3" width="20" height="14" rx="2"/></svg>'
)


def test_a_lucide_shaped_icon_comes_through_whole() -> None:
    """Every element and every attribute a real icon uses is on the allowlist."""
    kept = sanitise(LUCIDE)

    assert 'viewBox="0 0 24 24"' in kept
    assert 'stroke="currentColor"' in kept
    assert 'stroke-linejoin="round"' in kept
    assert '<path d="M12 12v-2"' in kept
    assert 'x="2"' in kept and 'rx="2"' in kept and 'width="20"' in kept


def test_a_script_and_a_handler_are_gone() -> None:
    """The whole point: markup on this board must not be able to run."""
    kept = sanitise(
        '<svg viewBox="0 0 24 24" onload="fetch(1)">'
        "<script>alert(1)</script>"
        '<path d="M1 1" onclick="alert(2)" href="/etc/passwd"/>'
        "</svg>"
    )

    assert "script" not in kept
    assert "onload" not in kept and "onclick" not in kept
    assert "href" not in kept
    assert '<path d="M1 1"' in kept


def test_markup_that_survives_as_nothing_is_refused() -> None:
    """An icon emptied of everything drawable draws nothing, silently. Say so."""
    with pytest.raises(ValueError, match="nothing this board draws"):
        sanitise('<svg viewBox="0 0 24 24"><image href="/tmp/x.png"/></svg>')

    with pytest.raises(ValueError, match="not SVG this board can read"):
        sanitise("<svg><path d=")

    with pytest.raises(ValueError, match="start with an <svg> element"):
        sanitise("<svgx><path d='M1 1'/></svgx>")


def test_a_widget_stores_the_sanitised_markup_not_what_arrived() -> None:
    """The Icon type is where every widget's icon goes through, so it is enough."""
    payload = ListPayload(icon='<svg viewBox="0 0 1 1"><script/><path d="M1 1"/></svg>')

    assert payload.icon is not None
    assert "script" not in payload.icon
    assert '<path d="M1 1"' in payload.icon

    with pytest.raises(ValidationError):
        ListPayload(icon="<svg><title>nothing</title></svg>")
