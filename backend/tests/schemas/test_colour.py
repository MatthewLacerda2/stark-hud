"""What the board accepts as a colour.

The validator earns its place twice over: it lets a colour carry its own alpha,
which is how text and chart marks are made to read over a moving background, and
it turns a typo into a sentence. Without it a misspelt colour is dropped by the
browser and the widget simply renders wrong, with nothing anywhere saying why.
"""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas.board import (
    BoxPayload,
    ChartPayload,
    ItemCreate,
    ListEntry,
    ListPayload,
    NotePayload,
)
from schemas.colour import TOKENS

TEXT = NotePayload(text="x")


@pytest.mark.parametrize(
    "colour",
    ["#fff", "#ffff", "#ffffff", "#ffffff80", "var(--chart-2)", "rgba(0, 0, 0, 0.5)", "white"],
)
def test_a_colour_the_browser_reads_is_accepted(colour):
    assert ItemCreate(payload=TEXT, color=colour).color == colour


@pytest.mark.parametrize("colour", ["#12345", "#gggggg", "blue; drop", "", "   ", "rgb("])
def test_anything_else_is_refused(colour):
    with pytest.raises(ValidationError):
        ItemCreate(payload=TEXT, color=colour)


def test_alpha_survives_everywhere_a_colour_is_taken():
    translucent = "#00ff8840"

    assert NotePayload(text="x", color=translucent).color == translucent
    assert BoxPayload(fill=translucent, stroke=translucent).stroke == translucent
    widget = ListPayload(title_color=translucent, icon_color=translucent, item_color=translucent)
    assert widget.item_color == widget.icon_color == translucent
    entry = ListEntry(
        title="x", title_color=translucent, body_color=translucent, icon_color=translucent
    )
    assert entry.title_color == entry.body_color == entry.icon_color == translucent
    assert ChartPayload(
        chart="bar", data=[{"a": 1}], x_key="a", series=["a"], colors=[translucent]
    ).colors == [translucent]


@pytest.mark.parametrize(
    ("name", "resolved"),
    [("accent", "var(--color-accent)"), ("chart-2", "var(--color-chart-2)")],
)
def test_a_token_name_becomes_the_variable_it_names(name, resolved):
    assert ItemCreate(payload=TEXT, color=name).color == resolved


@pytest.mark.parametrize("colour", ["acent", "chart-9", "cornflowerblue"])
def test_a_word_that_names_no_token_is_refused(colour):
    """A near miss used to validate as "some keyword" and vanish in the browser."""
    with pytest.raises(ValidationError):
        ItemCreate(payload=TEXT, color=colour)


def test_the_tokens_are_the_ones_the_stylesheet_defines():
    """The gate that keeps this list honest.

    A token accepted here and missing from the stylesheet resolves to a variable
    nothing defines, and the browser drops it without a word. Read the real file
    rather than trusting the copy, so adding a colour to one and not the other
    fails a gate instead of a widget.
    """
    css = Path(__file__).parents[3] / "frontend" / "src" / "styles.css"
    theme = css.read_text(encoding="utf-8").split("@theme inline", 1)[1]
    defined = set(re.findall(r"^\s*--color-([a-z0-9-]+):", theme, re.M))

    assert defined == set(TOKENS)
