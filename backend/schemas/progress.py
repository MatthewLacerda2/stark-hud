"""What a progress bar shows: how far along something is.

Its own module because ``schemas.payloads`` sits at the house's line ceiling,
and because this one carries a rule about its own two ends.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from schemas.colour import Colour
from schemas.icon import Icon

# Which end of the bar the icon sits at. The start is the default because that
# is where a line starts being read.
IconSide = Literal["start", "end"]


class ProgressPayload(BaseModel):
    """One number between two others, drawn as a bar filling up.

    It is a gauge laid flat, and it exists because the flat shape fits a strip
    of board no ring can use: a gauge is as tall as it is wide, a bar is not.

    The ends are labelled with numbers, not with the value. The fill already
    says how far along it is; what the bar cannot say is how far it is going.
    So the far end names ``max``, and the near end names ``min`` only when it is
    not zero — a bar starting from nothing needs no label saying so. Either end
    can be given its own text instead (``min_label``, ``max_label``), which is
    how a deadline says "Friday" rather than "7", and an empty string hides it.

    Updating it means writing it again, as with a chart: whoever has the number
    sends it, and the board never polls.
    """

    # Set here rather than inherited, for the reason the chart gives: the base in
    # ``payloads`` cannot be imported from here without a cycle.
    model_config = ConfigDict(extra="forbid")

    kind: Literal["progress"] = "progress"
    value: float
    min: float = 0
    max: float = 100
    # Drawn above the bar. Left out, the bar takes that height too.
    title: str | None = None
    icon: Icon | None = None
    icon_side: IconSide = "start"
    # Text for either end in place of the number. None draws the number; an
    # empty string draws nothing.
    min_label: str | None = None
    max_label: str | None = None
    # The filled part. Left out it is the translucent white the gauges use.
    color: Colour | None = None
    # The part not reached yet. Left out it is a fainter white — see the gauge's
    # `unfilled` for why it stays see-through.
    unfilled: Colour | None = None

    @model_validator(mode="after")
    def _ends_in_order(self) -> "ProgressPayload":
        """Refuse a bar whose far end is not past its near one.

        A value outside the two ends is fine, and is drawn empty or full: a run
        that overshoots its budget is finished, not malformed. Ends the wrong
        way round are a mistake in the call, and there is no bar to draw.
        """
        if self.max <= self.min:
            raise ValueError(f"max ({self.max}) must be greater than min ({self.min})")
        return self
