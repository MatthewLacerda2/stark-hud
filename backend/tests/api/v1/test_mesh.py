"""Serving a wireframe, and the one widget that takes itself off the board."""

from pathlib import Path

from httpx import AsyncClient

ITEMS = "/api/v1/board/items"
TRIANGLE = "o tri\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"


async def _add_mesh(client: AsyncClient, path: str) -> str:
    """Create a mesh item and return its id."""
    body = {"payload": {"kind": "mesh", "path": path}}
    return (await client.post(ITEMS, json=body)).json()["id"]


async def _ids(client: AsyncClient) -> list[str]:
    """Every widget on the board, by id."""
    return [item["id"] for item in (await client.get(ITEMS)).json()]


def _model(tmp_path: Path, text: str = TRIANGLE) -> str:
    """Write an OBJ and give back its path."""
    target = tmp_path / "model.obj"
    target.write_text(text)
    return str(target)


async def test_a_real_file_comes_back_as_parts(client: AsyncClient, tmp_path: Path) -> None:
    """The browser is handed points and lines, never the path they came from."""
    item_id = await _add_mesh(client, _model(tmp_path))
    body = (await client.get(f"/api/v1/mesh/{item_id}")).json()
    assert [part["name"] for part in body["parts"]] == ["tri"]
    assert len(body["parts"][0]["edges"]) // 2 == 3
    assert "model.obj" not in str(body)


async def test_a_vanished_file_removes_the_widget(client: AsyncClient, tmp_path: Path) -> None:
    """The mesh widget is the one that goes, rather than drawing a placeholder."""
    path = _model(tmp_path)
    item_id = await _add_mesh(client, path)
    Path(path).unlink()

    response = await client.get(f"/api/v1/mesh/{item_id}")
    assert response.status_code == 404
    assert "model.obj" in response.json()["detail"]
    assert item_id not in await _ids(client)


async def test_a_removal_says_so_in_the_inbox(client: AsyncClient, tmp_path: Path) -> None:
    """A widget that disappears unwatched still leaves a line naming the file."""
    path = _model(tmp_path)
    item_id = await _add_mesh(client, path)
    Path(path).unlink()
    await client.get(f"/api/v1/mesh/{item_id}")

    inbox = (await client.get("/api/v1/notifications")).json()["notifications"]
    assert any(path in (note["body"] or "") for note in inbox)


async def test_a_file_that_is_not_a_mesh_is_422(client: AsyncClient, tmp_path: Path) -> None:
    """A real file the board cannot draw is a different answer from a missing one."""
    item_id = await _add_mesh(client, _model(tmp_path, "v 0 0 0\nv 1 1 1\n"))
    assert (await client.get(f"/api/v1/mesh/{item_id}")).status_code == 422
    # Still on the board: the file is there, so there is something to fix.
    assert item_id in await _ids(client)


async def test_a_note_is_not_a_mesh(client: AsyncClient) -> None:
    """Only mesh widgets have geometry to serve."""
    note = (await client.post(ITEMS, json={"payload": {"kind": "note", "text": "x"}})).json()
    assert (await client.get(f"/api/v1/mesh/{note['id']}")).status_code == 404


async def test_unknown_id_is_404(client: AsyncClient) -> None:
    """An id that never existed is not found."""
    assert (await client.get("/api/v1/mesh/nope")).status_code == 404
