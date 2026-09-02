"""Sanitising an icon that arrives as SVG markup.

The board has no authentication, on purpose: anything on the LAN can write to
it. Markup handed straight through to the kiosk would turn "write to a widget"
into "run JavaScript on the television", so nothing a caller sends is passed
through. It is parsed here and a new document is built from an allowlist —
a `script`, a `foreignObject`, an `image`, an `on...` handler, a `style`, an
`href` simply have nowhere to go, without anyone having to enumerate them.

The allowlist is the shape lucide icons already have: they ship as arrays of
elements like ``["path", {"d": ...}]``, never as files. So an icon pasted from
anywhere on the web is built out of exactly these, and a caller who wants one
lucide does not have can draw it in the same vocabulary.

Standard library only. A parser dependency here would be a third party sitting
between the LAN and the television.
"""

import xml.etree.ElementTree as ElementTree

_SVG_NS = "http://www.w3.org/2000/svg"

# What may be drawn: shapes and the group that positions them. Nothing that
# loads, runs, or reaches outside the markup.
ELEMENTS = frozenset(
    {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
)

# What a shape may say about itself: where it is, how big, and how it is
# painted. `fill` and `stroke` are here so a caller can pass `currentColor` and
# let the widget decide the colour.
ATTRIBUTES = frozenset(
    {
        "d",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "width",
        "height",
        "rx",
        "ry",
        "cx",
        "cy",
        "r",
        "points",
        "transform",
        "fill",
        "fill-rule",
        "clip-rule",
        "stroke",
        "stroke-width",
        "stroke-linecap",
        "stroke-linejoin",
    }
)

# `viewBox` maps the icon's own coordinates onto the box it is drawn in, which
# only means anything on the root element.
ROOT_ONLY = frozenset({"viewBox"})


def looks_like_svg(value: str) -> bool:
    """Whether a caller meant markup, rather than a name or a path.

    Asked before validating so the three forms of an icon can be told apart and
    each refused in its own words.
    """
    return value.lstrip().startswith("<svg")


def _local(name: str) -> str:
    """A tag or attribute name with the namespace ElementTree prefixed onto it gone."""
    return name.rsplit("}", 1)[-1]


def _keep(source: ElementTree.Element, *, root: bool) -> ElementTree.Element:
    """Rebuild one element and its children from the allowlist.

    Built up rather than pruned down: an element only exists in the result
    because something put it there, so anything the lists do not name is gone
    without being named itself. Text is not copied either — nothing in an icon
    is words.
    """
    allowed = ATTRIBUTES | ROOT_ONLY if root else ATTRIBUTES
    kept = ElementTree.Element(_local(source.tag))
    for name, value in source.attrib.items():
        if _local(name) in allowed:
            kept.set(_local(name), value)
    for child in source:
        if _local(child.tag) in ELEMENTS:
            kept.append(_keep(child, root=False))
    return kept


def sanitise(markup: str) -> str:
    """Return the drawable part of ``markup``, or say why there is none.

    Refused rather than emptied: an icon that survives as nothing draws as
    nothing, and whoever pasted the wrong thing would never find out.
    """
    if "<!DOCTYPE" in markup or "<!ENTITY" in markup:
        raise ValueError("that SVG declares a doctype or an entity, which an icon has no use for")
    try:
        parsed = ElementTree.fromstring(markup)
    except ElementTree.ParseError as exc:
        raise ValueError(f"that is not SVG this board can read: {exc}") from exc
    if _local(parsed.tag) != "svg":
        raise ValueError("an SVG icon has to start with an <svg> element")

    kept = _keep(parsed, root=True)
    if len(kept) == 0:
        raise ValueError(
            "that SVG has nothing this board draws: it may only contain "
            f"{', '.join(sorted(ELEMENTS - {'svg'}))}"
        )
    # Named back as SVG, so what we store is a document in its own right rather
    # than a fragment that only means something where it happens to be pasted.
    kept.set("xmlns", _SVG_NS)
    return ElementTree.tostring(kept, encoding="unicode")
