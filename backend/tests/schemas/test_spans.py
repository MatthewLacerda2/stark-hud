"""A pair of instants, and the two ways a caller can fill one in wrongly.

Tested against the models rather than the helper, because the point of moving
the rule into the schema is that it holds wherever the type is built — over the
API as much as through MCP, and neither path goes anywhere near the tool that
used to do the checking.
"""

import pytest
from pydantic import ValidationError

from schemas.board import Countdown, GanttBar

AWARE = "2026-09-04T18:00:00Z"
NAIVE = "2026-09-04T18:00:00"
LATER_NAIVE = "2026-09-04T19:00:00"


def test_a_countdown_may_be_a_moment_with_no_end() -> None:
    """The ordinary shape of an entry, and not something to refuse."""
    assert Countdown(title="doorbell", start=NAIVE).end is None


def test_two_ends_that_disagree_about_timezone_are_refused() -> None:
    """The bug: this pair used to reach a comparison that raises TypeError."""
    with pytest.raises(ValidationError) as raised:
        Countdown(title="sauce", start=NAIVE, end=AWARE)
    assert "names a timezone on one end and not the other" in str(raised.value)
    assert "'sauce'" in str(raised.value)


def test_the_same_pair_the_other_way_round() -> None:
    """Aware start, naive end. The comparison breaks on either ordering."""
    with pytest.raises(ValidationError):
        Countdown(title="sauce", start=AWARE, end=NAIVE)


def test_an_end_at_or_before_its_start_is_refused() -> None:
    """Moved into the schema with the other rule, so the API path refuses it too."""
    with pytest.raises(ValidationError) as raised:
        Countdown(title="sauce", start=LATER_NAIVE, end=NAIVE)
    assert "would end at or before it starts" in str(raised.value)


def test_a_pair_that_agrees_is_left_alone() -> None:
    """Both naive and both aware are each a span this can order."""
    assert Countdown(title="bake", start=NAIVE, end=LATER_NAIVE).end is not None
    assert Countdown(title="bake", start=AWARE, end="2026-09-04T19:00:00Z").end is not None


def test_the_gantt_refuses_the_same_pair_in_the_same_words() -> None:
    """The reason the rule is shared: one mistake should not have two wordings."""
    with pytest.raises(ValidationError) as bar:
        GanttBar(title="sauce", start=NAIVE, end=AWARE)
    with pytest.raises(ValidationError) as entry:
        Countdown(title="sauce", start=NAIVE, end=AWARE)
    assert "names a timezone on one end and not the other" in str(bar.value)
    assert "names a timezone on one end and not the other" in str(entry.value)
