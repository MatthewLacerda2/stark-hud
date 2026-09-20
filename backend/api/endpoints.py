"""Compose the versioned API router.

Nothing here is authenticated: the board is open to the LAN by design.
"""

from fastapi import APIRouter

from api.v1 import board, command, entries, media, mesh, notifications, speech

api_router = APIRouter()
api_router.include_router(board.router)
api_router.include_router(command.router)
# Both of these hang routes off ``/board`` for one kind of widget: the lines a
# list or a countdown keeps, and what the browser says a player is doing. They
# are their own files rather than more of the generic board router, which should
# not have to ask what kind of thing it was handed.
api_router.include_router(entries.router)
api_router.include_router(media.playback_router)
api_router.include_router(media.router)
api_router.include_router(mesh.router)
api_router.include_router(notifications.router)
api_router.include_router(speech.router)
