"""FastAPI application entrypoint.

Middleware order (outermost first): CORS -> request logging.
The versioned API router is mounted at ``/api/v1``, the board socket lives at
``/ws``, and the MCP server at ``/mcp``. There is no database: the board is held
in memory and mirrored to a ``.hud`` file, read back at startup.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.endpoints import api_router
from core.config import get_settings
from core.hub import hub
from core.logging_middleware import LoggingMiddleware
from core.refusal import BoardRefusal
from hud_mcp.server import build_app as build_mcp_app
from hud_mcp.server import server as board_tools
from repositories import board as repo
from repositories import notifications as notifications_repo
from schemas.board import BoardSnapshot
from services import persistence

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


def _refusal_handler(_request: Request, exc: Exception) -> JSONResponse:
    """The one answer to the board saying no.

    There were ten of these, several character-identical, and each existed only
    to put a number in front of a sentence the exception had already written.
    The number belongs to the exception now — see ``core.refusal`` — so this
    reads it off rather than knowing it, and a new refusal needs nothing here.
    """
    assert isinstance(exc, BoardRefusal)
    return JSONResponse(status_code=exc.status, content={"detail": str(exc), **exc.extra()})


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

    # One registration for every refusal the board makes: Starlette walks the
    # MRO looking for a handler, so a subclass of ``BoardRefusal`` lands here
    # without being named. That is the point — the ten handlers this replaces
    # meant a refusal nobody remembered to register came out as a 500.
    app.add_exception_handler(BoardRefusal, _refusal_handler)

    app.add_middleware(LoggingMiddleware)
    # The one introduction between the two surfaces. `api/` and `hud_mcp/` sit
    # at the same height and neither may import the other — but the command
    # endpoint has to reach the board's tool catalogue, and this is the
    # composition root, which is the place that is allowed to know about both.
    app.state.board = board_tools()
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


def _register_socket(app: FastAPI) -> None:
    """Attach the board socket."""

    @app.websocket("/ws")
    async def board_socket(socket: WebSocket) -> None:
        """Push the current board on connect, then stream every change."""
        await hub.connect(socket)
        try:
            snapshot = BoardSnapshot(
                items=repo.list_items(),
                showing=repo.showing(),
                background=repo.get_background(),
                ink=repo.get_ink(),
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
