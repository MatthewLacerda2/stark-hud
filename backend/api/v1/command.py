"""Take a sentence typed at the board and let a fast model carry it out.

Open, like everything else here: the board has no auth by design, so anything
on the wifi can drive it — and, through this one, spend the owner's Gemini
quota. Known and accepted rather than discovered later; the day that stops
being acceptable it is the board's auth story and not this route's.
"""

from fastapi import APIRouter, HTTPException, Request, status

from schemas.command import CommandRead, CommandRequest
from services import command as service

router = APIRouter(prefix="/command", tags=["command"])


@router.post("", status_code=status.HTTP_200_OK)
async def run_command(command: CommandRequest, request: Request) -> CommandRead:
    """Do what the sentence says, and report what was called doing it.

    502 rather than 500 when it fails: every one of these is the vendor saying
    no — no key, a refused key, no quota, no answer in time — and the detail is
    one sentence naming the thing to go and fix. A 500 would say the board is
    broken, and it is not; nothing else on it is affected.

    Where the board's tools come from is `main`'s business, not this route's:
    `api/` and `hud_mcp/` are the same height in this stack and neither may
    import the other, so the composition root introduces them and leaves the
    result on app state.
    """
    try:
        return await service.run(command.prompt, request.app.state.board, command.model)
    except service.CommandError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
