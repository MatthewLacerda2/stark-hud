"""FastAPI application entrypoint.

Middleware order (outermost first): CORS -> rate limiting -> request logging.
The versioned API router is mounted at ``/api/v1``, the board socket lives at
``/ws``, and the MCP server at ``/mcp``. There is no database: the board is in
memory and starts empty.
"""

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
from services.board import SlotTakenError
from services.placement import BoardFullError

APP_NAME = "stark-hud"

# Built once at import so the mounted app and the lifespan below are the same
# object: a mounted sub-app's lifespan is not run by the parent automatically,
# and without it the MCP session manager never starts.
mcp_app = build_mcp_app()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Run the MCP session manager for the life of the process."""
    async with mcp_app.router.lifespan_context(mcp_app):
        yield


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
            snapshot = [item.model_dump(mode="json") for item in repo.list_items()]
            await socket.send_json({"event": "board.snapshot", "data": snapshot})
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            await hub.disconnect(socket)


app = create_app()
