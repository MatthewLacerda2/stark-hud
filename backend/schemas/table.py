"""What a table shows: named columns, and rows read across them.

Its own module for the reason progress has one — ``schemas.payloads`` is at the
house's line ceiling — and because the columns are a model of their own.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.colour import Colour
from schemas.icon import Icon

# Which edge of its column a cell sits against. Numbers belong on the right,
# where their digits line up and a long one is visibly long; words belong on the
# left, where the eye starts.
Align = Literal["left", "right"]


class TableColumn(BaseModel):
    """One column: where its cells come from, what it is called, how it sits.

    ``key`` names the field to read out of each row, the way a chart's ``x_key``
    does. A column is therefore a question asked of every row, and a row that
    cannot answer draws an empty cell rather than breaking the table.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    # The heading. Left out, the key is the heading — which is usually right,
    # because a key worth reading out of a row is worth reading at the top of it.
    label: str | None = None
    align: Align = "left"
    # This column's share of the width, against the other columns' shares. Every
    # column asks for one part unless it says otherwise, so a name column that
    # needs the room asks for two.
    #
    # Shares rather than measured widths so the heading and the rows line up:
    # they are two grids, because the heading must stay put while the rows
    # scroll, and two grids only agree on a column when neither is sizing it
    # from what happens to be in it.
    width: float = Field(default=1, gt=0)


class TablePayload(BaseModel):
    """Rows of text under named columns.

    Not a list with the spaces counted: a list is one string per line, so
    lining the numbers up would mean padding them and hoping the font is
    monospaced, and a column could never be given its own alignment. Here the
    columns are the widget's structure, and the rows only carry the text.

    Every cell is text, already in the units the writer chose — "1.7 GB", "<1%".
    The board has no opinion about how a number should read; whoever measured it
    does, and a table that reformatted the figures would be guessing.

    Written whole, like a chart: whoever has the rows sends all of them.
    """

    # Set here rather than inherited, as the chart and progress do: the base in
    # ``payloads`` cannot be imported from here without a cycle.
    model_config = ConfigDict(extra="forbid")

    kind: Literal["table"] = "table"
    title: str | None = None
    # A name from the icon set, a path to a picture, or SVG markup, drawn beside
    # the heading. A picture is served by this item's id, never by its path.
    icon: Icon | None = None
    columns: list[TableColumn] = []
    rows: list[dict[str, str]] = []
    empty: str | None = None
    # The widget-wide colours, following the list's rule: the heading, the icon
    # beside it, and everything inside the table. Any left out falls back to the
    # widget's own colour, so a plain table needs no colours at all.
    title_color: Colour | None = None
    icon_color: Colour | None = None
    row_color: Colour | None = None
