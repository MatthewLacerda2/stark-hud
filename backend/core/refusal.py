"""The board saying no, in one shape.

Every refusal this board makes is the same event: a change it will not make
because it could not make it whole, and a sentence saying why. What differed
between them was only the number on the front — 409 for a change that collides
with the board as it stands, 404 for one naming something that is not there,
422 for one naming something the board cannot draw.

That number used to live in ``main.py``, one handler per exception, ten of them,
several character-identical. So the status was a property of the *handler*, and
adding an exception without adding a handler beside it produced a 500 — which is
the board claiming it broke when in fact it had an opinion.

Here it is a property of the exception, which is the thing that knows. ``main``
registers one handler for this base and Starlette's lookup walks the MRO, so a
new refusal is a class with a ``status`` and nothing else to remember.
"""

from __future__ import annotations


class BoardRefusal(Exception):
    """A change the board declines, carrying the status that says what kind.

    ``409`` is the common case and so the default: the board as it stands will
    not take this. Subclasses that mean something else say so in one line.
    """

    status: int = 409

    def extra(self) -> dict[str, object]:
        """Anything past the sentence that a caller can act on.

        A blind caller — every caller here is blind, the board is on a
        television in another room — can only act on what comes back. Mostly the
        sentence is the whole of it, so this is empty by default; a refusal that
        can hand back the shape of the free space, or the id of the widget in
        the way, overrides it and that lands beside ``detail`` in the JSON.
        """
        return {}
