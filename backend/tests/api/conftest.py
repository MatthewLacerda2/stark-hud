"""Shared API-test fixtures.

Nothing is authenticated and nothing is overridden: the app under test is the
same app that ships, talking to the same in-memory board.
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTPX client bound to the ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
