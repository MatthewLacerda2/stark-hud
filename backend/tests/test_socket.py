"""What a client is handed the moment it connects.

The snapshot has changed shape twice and broken silently both times: the page
connected, failed to read a field that was not there, and sat on "Reconnecting"
while the board looked simply empty. Nothing else checks this contract.
"""

from fastapi.testclient import TestClient

from main import app


def test_snapshot_carries_everything_a_client_needs() -> None:
    """Every part of the board a fresh client needs, in one message."""
    # No lifespan: the socket route does not need the MCP session manager, and
    # that manager refuses to start twice in one test session.
    with TestClient(app).websocket_connect("/ws") as socket:
        message = socket.receive_json()

    assert message["event"] == "board.snapshot"
    assert set(message["data"]) == {"items", "background", "ink", "notifications"}


def test_a_new_item_reaches_a_connected_client() -> None:
    """A change made over HTTP arrives on the socket without being asked for."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as socket:
        socket.receive_json()  # the snapshot
        client.post("/api/v1/board/items", json={"payload": {"kind": "note", "text": "hi"}})
        message = socket.receive_json()

    assert message["event"] == "item.created"
    assert message["data"]["payload"]["text"] == "hi"
