"""Compose the versioned API router.

Nothing here is authenticated: the board is open to the LAN by design.
"""

from fastapi import APIRouter

from api.v1 import board, media, notifications

api_router = APIRouter()
api_router.include_router(board.router)
api_router.include_router(media.router)
api_router.include_router(notifications.router)
