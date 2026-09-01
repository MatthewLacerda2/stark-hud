"""What the board accepts as a colour.

The validator earns its place twice over: it lets a colour carry its own alpha,
which is how text and chart marks are made to read over a moving background, and
it turns a typo into a sentence. Without it a misspelt colour is dropped by the
browser and the widget simply renders wrong, with nothing anywhere saying why.
"""

import pytest
from pydantic import ValidationError

from schemas.board import BoxPayload, ChartPayload, ItemCreate, ListPayload, NotePayload

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
    assert ListPayload(title_color=translucent, item_color=translucent).item_color == translucent
    assert ChartPayload(
        chart="bar", data=[{"a": 1}], x_key="a", series=["a"], colors=[translucent]
    ).colors == [translucent]
