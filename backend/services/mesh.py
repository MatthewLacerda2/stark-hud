"""Which model files the mesh widget can show, and what happens when one goes.

Nothing here reads a model. The file is sent to the browser as it is and
three.js reads it there — a glTF carries its parts, their pivots and their
animation, and every step on this side that turned a model into something
simpler was a step that threw some of that away. What is left for the server
is the part a browser cannot do: find the file, say what kind it is, and
notice when it has gone.
"""

from pathlib import Path

from repositories import board as repo
from schemas.board import ItemRead
from schemas.mesh import MODEL_TYPES
from schemas.notifications import NotificationCreate
from services import events, notifications


def file_of(path: str) -> tuple[Path, str] | None:
    """The file to send and what to call it, or ``None`` when it is not there."""
    target = Path(path)
    if not target.is_file():
        return None
    return target, MODEL_TYPES.get(target.suffix.lower(), "application/octet-stream")


async def forget(item: ItemRead, path: str) -> str:
    """Take a mesh widget off the board because its file is no longer there.

    The mesh widget is the one file-backed widget that does this. A picture or a
    video whose file has moved draws a placeholder naming the path and waits, on
    the grounds that the file may come back; this one removes itself, which the
    owner of the board asked for so that a board left running does not silently
    fill up with widgets pointing at models that were tidied away months ago.

    It is worth a later session knowing what that costs, because the cost is not
    theoretical here. A 404 means "not visible from inside the container right
    now", which is not the same as "deleted": `/mnt/d_drive` is a bind mount and
    can be late, a re-export unlinks the file before it writes the new one, and
    only `${HOME}` and that drive are mounted at all. In each of those the file
    is fine and the widget goes anyway, taking its place, size and description
    with it.

    Which is why this announces itself. Removal is written to the inbox naming
    the file, so a widget that disappears while nobody was watching leaves a line
    behind saying which model it was — the board is reviewed by looking at it,
    and a widget that simply stops being there tells nobody anything.

    Removing the item is all that is needed to take it out of `board.hud` too:
    the repository marks the store dirty and the flusher writes the file.
    """
    repo.remove(item.id)
    await events.removed(item.id)
    await notifications.create(
        NotificationCreate(
            title="Mesh widget removed",
            body=f"{path} is no longer there.",
            level="warn",
            source="mesh",
        )
    )
    return f"{path} is gone, so the widget showing it has been removed from the board."
