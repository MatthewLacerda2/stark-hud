"""The one rule about a pair of instants, for every widget that holds one.

A start and an end are two fields a caller fills in separately, so they can
disagree — and the two ways they disagree are the same wherever they appear.
Both of them have to be refused before anything compares them, because the
comparison itself is what breaks: Python will not order an aware datetime
against a naive one, and an uncaught ``TypeError`` reaches whoever asked as a
crash rather than as the sentence they can act on.

Shared rather than written twice, and the sentence is the reason. Two copies of
a rule drift into two different wordings for one mistake, and the wording is the
whole product here — the caller is a model that cannot see the board and has
only this line to work out which of two fields it typed wrongly.

It lives in its own module rather than beside either caller because
``schemas.payloads`` is at the house's line ceiling, which is the lint doing its
job: it fires on the sum, and what it is pointing at is that a rule shared by
the gantt and the countdown belongs to neither of them.
"""

from datetime import datetime


def refuse_bad_span(title: str, start: datetime, end: datetime | None) -> None:
    """Raise a readable ``ValueError`` when two instants do not make a span.

    ``end`` may be ``None``: a thing with a start and no end is a moment rather
    than a window, which is a countdown entry's ordinary shape and not a fault.
    """
    if end is None:
        return
    # Both aware or both naive. Checked first, because the ordering below is
    # exactly what raises on a mixed pair.
    if (start.tzinfo is None) != (end.tzinfo is None):
        raise ValueError(
            f"{title!r} names a timezone on one end and not the other; give both or neither"
        )
    if end <= start:
        raise ValueError(f"{title!r} would end at or before it starts")
