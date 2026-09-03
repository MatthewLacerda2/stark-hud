"""FastAPI application entrypoint.

Middleware order (outermost first): CORS -> rate limiting -> request logging.
The versioned API router is mounted at ``/api/v1``, the board socket lives at
``/ws``, and the MCP server at ``/mcp``. There is no database: the board is held
in memory and mirrored to a ``.hud`` file, read back at startup.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.endpoints import api_router
from core.config import get_settings
from core.hub import hub
from core.logging_middleware import LoggingMiddleware
from core.rate_limiter import limiter
from hud_mcp.server import build_app as build_mcp_app
from repositories import board as repo
from repositories import notifications as notifications_repo
from schemas.board import BoardSnapshot
from services import persistence
from services.arrange import RepeatedTargetError, UnknownTargetError
from services.board import KeyTakenError, MissingFileError, SlotTakenError
from services.notifications import BadIconError
from services.placement import BoardFullError, NoRoomError

APP_NAME = "stark-hud"

# Built once at import so the mounted app and the lifespan below are the same
# object: a mounted sub-app's lifespan is not run by the parent automatically,
# and without it the MCP session manager never starts.
mcp_app = build_mcp_app()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Restore the board, run the MCP session manager, and write on the way out.

    The final save is what makes a clean stop lose nothing; the flusher is what
    covers the other kind, where nothing gets to run on the way out.
    """
    persistence.restore()
    flush = asyncio.create_task(persistence.flusher(get_settings().STATE_FLUSH_SECONDS))
    try:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
    finally:
        flush.cancel()
        persistence.save()


def _rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a 429 JSON response when a rate limit is exceeded."""
    return JSONResponse(status_code=429, content={"detail": f"Rate limit exceeded: {exc.detail}"})


def _board_full_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Return 409 with the free space, so the caller can pick a smaller size."""
    assert isinstance(exc, BoardFullError)
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc), "cells_free": exc.cells_free, "requested": [exc.w, exc.h]},
    )


def _slot_taken_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Return 409 when an explicit placement collides or falls outside the grid."""
    assert isinstance(exc, SlotTakenError)
    return JSONResponse(status_code=409, content={"detail": str(exc)})


def _key_taken_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Return 409 naming the widget that already holds the key."""
    assert isinstance(exc, KeyTakenError)
    return JSONResponse(status_code=409, content={"detail": str(exc), "holder": exc.holder.id})


def _no_room_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Return 409 naming what two widgets an arrangement would have stacked."""
    return JSONResponse(status_code=409, content={"detail": str(exc)})


def _unknown_target_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Return 404 when a batch names a widget that is not there."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


def _missing_file_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Return 404 when a background points at a path that is not there."""
    assert isinstance(exc, MissingFileError)
    return JSONResponse(status_code=404, content={"detail": str(exc)})


def _bad_icon_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Return 422 naming the icons that exist, rather than drawing nothing."""
    assert isinstance(exc, BadIconError)
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(title=APP_NAME, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_exception_handler(BoardFullError, _board_full_handler)
    app.add_exception_handler(SlotTakenError, _slot_taken_handler)
    app.add_exception_handler(KeyTakenError, _key_taken_handler)
    app.add_exception_handler(NoRoomError, _no_room_handler)
    app.add_exception_handler(RepeatedTargetError, _no_room_handler)
    app.add_exception_handler(UnknownTargetError, _unknown_target_handler)
    app.add_exception_handler(MissingFileError, _missing_file_handler)
    app.add_exception_handler(BadIconError, _bad_icon_handler)

    app.add_middleware(LoggingMiddleware)
    app.include_router(api_router, prefix="/api/v1")
    app.mount("/mcp", mcp_app)

    _register_baseline_routes(app)
    _register_socket(app)
    return app


def _register_baseline_routes(app: FastAPI) -> None:
    """Attach the unversioned baseline endpoints."""

    @app.get("/")
    async def root() -> dict[str, str]:
        """Service identity and status."""
        return {"name": APP_NAME, "status": "ok"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness probe (intentionally not logged)."""
        return {"status": "healthy"}

    @app.get("/security.txt", response_class=PlainTextResponse)
    async def security_txt() -> str:
        """Plaintext security contact (see securitytxt.org)."""
        return "Contact: mailto:security@example.com\nExpires: 2027-01-01T00:00:00Z\n"


def _register_socket(app: FastAPI) -> None:
    """Attach the board socket."""

    @app.websocket("/ws")
    async def board_socket(socket: WebSocket) -> None:
        """Push the current board on connect, then stream every change."""
        await hub.connect(socket)
        try:
            snapshot = BoardSnapshot(
                items=repo.list_items(),
                background=repo.get_background(),
                notifications=notifications_repo.list_all(),
            )
            await socket.send_json(
                {"event": "board.snapshot", "data": snapshot.model_dump(mode="json")}
            )
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            await hub.disconnect(socket)


app = create_app()
