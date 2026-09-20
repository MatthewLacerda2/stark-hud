"""Adding one line to a widget that keeps its lines, over HTTP.

Two widgets on this board hold what they were given rather than being rewritten
whole: a list somebody keeps, and a countdown stack. Adding to one used to be
something only an MCP client could do — the rule lived inside the tools — so the
agent feeding the panels over HTTP could rewrite a list whole or not touch it,
and rewriting whole is exactly what a kept list cannot survive. It has the same
two calls as a session does now.

Its own router rather than a pair of routes in the generic board router, for the
reason ``playback`` moved to ``api/v1/media.py``: a route about one kind of
widget belongs with that kind, not behind a check of what it was handed.
"""

from fastapi import APIRouter, HTTPException, status

from repositories import board as repo
from schemas.board import ItemRead
from schemas.entries import EntryCreate
from services import entries as service
from services.entries import BadEntryError, NoEntryError, NotKeptError

router = APIRouter(prefix="/board", tags=["board"])


def _kept_or_404(target: str) -> ItemRead:
    """The widget this line is for, by id or by key, or a 404 saying why not.

    By key as well as by id, everywhere, because a repeating writer knows its
    panel's name and never its id — that is the whole of what a key is for.
    """
    item = repo.get(target) or repo.get_by_key(target)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    try:
        service.kept(item)
    except NotKeptError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return item


@router.post("/items/{target}/entries", response_model=ItemRead)
async def add_entry(target: str, payload: EntryCreate) -> ItemRead:
    """Add one line to the end of a list, or one thing to a countdown stack.

    Appending, which is the point: the caller does not have to know what is
    already there, and nothing anybody else put there is lost. `target` is the
    widget's id or its key.

    Which fields mean anything is decided by the widget. A countdown entry needs
    a `start`; a list line takes a `body` and its own colours. Sending one kind's
    fields to the other kind is a 422 saying so, rather than a field quietly
    dropped and a caller that thinks it wrote something.
    """
    item = _kept_or_404(target)
    try:
        written, _ = await service.append(item, payload)
    except (BadEntryError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return written


@router.delete("/items/{target}/entries/{title}", response_model=ItemRead)
async def remove_entry(target: str, title: str) -> ItemRead:
    """Take one line out, naming it as it reads on the screen.

    Matched on the text, ignoring case and surrounding space: what is being
    removed is something readable from the sofa, not an index nobody there can
    count. A 404 names what the widget actually holds.
    """
    item = _kept_or_404(target)
    try:
        written, _ = await service.drop(item, title)
    except NoEntryError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return written
