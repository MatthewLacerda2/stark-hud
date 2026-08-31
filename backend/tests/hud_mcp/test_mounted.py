"""The MCP server as mounted, not just as a bag of tools.

A mounted sub-app's lifespan is not run by the parent automatically, and when it
is missing the session manager never starts and every /mcp request fails. This
covers that wiring.

One test, not two: the session manager refuses to ``run()`` twice on the same
instance, and ``mcp_app`` is built once at import. That is fine for a process
that starts once, but it means the lifespan can only be entered once per test
session.
"""

from httpx import ASGITransport, AsyncClient

from main import app, lifespan

HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}


async def test_mcp_is_reachable_over_http_under_the_app_lifespan() -> None:
    """The mount answers on /mcp, so a session on another machine can connect."""
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/mcp/", json=INITIALIZE, headers=HEADERS)

    assert response.status_code == 200
    assert "stark-hud" in response.text
