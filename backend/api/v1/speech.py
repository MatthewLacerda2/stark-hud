"""Serve the lines the board has been told to say.

Addressed by id, like every other file this API hands out: the MP3 sits in a
directory the backend owns and its path never appears in a URL. A line that has
already aged out 404s, which is ordinary rather than an error — by the time a
browser is late enough to miss one, the moment to say it has passed anyway.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from services import speech as service

router = APIRouter(prefix="/speech", tags=["speech"])


@router.get("/{speech_id}")
async def get_speech(speech_id: str) -> FileResponse:
    """Stream one spoken line, for the page that is going to play it."""
    path = service.audio_path(speech_id)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such spoken line")
    return FileResponse(path, media_type="audio/mpeg")
