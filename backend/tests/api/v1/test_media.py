"""Serving local media, and failing visibly when the file is gone."""

from pathlib import Path

from httpx import AsyncClient

ITEMS = "/api/v1/board/items"


async def _add_image(client: AsyncClient, path: str) -> str:
    """Create an image item and return its id."""
    body = {"payload": {"kind": "image", "path": path}}
    return (await client.post(ITEMS, json=body)).json()["id"]


async def test_existing_file_is_served(client: AsyncClient, tmp_path: Path) -> None:
    """A real path streams its bytes back."""
    target = tmp_path / "pic.png"
    target.write_bytes(b"not-really-a-png")
    item_id = await _add_image(client, str(target))
    response = await client.get(f"/api/v1/media/{item_id}")
    assert response.status_code == 200
    assert response.content == b"not-really-a-png"


async def test_vanished_file_404s_with_the_path(client: AsyncClient, tmp_path: Path) -> None:
    """A file that moved after the item was made says so, instead of 500ing."""
    item_id = await _add_image(client, str(tmp_path / "gone.png"))
    response = await client.get(f"/api/v1/media/{item_id}")
    assert response.status_code == 404
    assert "gone.png" in response.json()["detail"]


async def test_a_note_is_not_media(client: AsyncClient) -> None:
    """Only image and video items expose bytes."""
    note = (await client.post(ITEMS, json={"payload": {"kind": "note", "text": "x"}})).json()
    assert (await client.get(f"/api/v1/media/{note['id']}")).status_code == 404


async def test_unknown_id_is_404(client: AsyncClient) -> None:
    """An id that never existed is not found."""
    assert (await client.get("/api/v1/media/nope")).status_code == 404


async def _add_feed(client: AsyncClient, icon: str) -> str:
    """Create a feed carrying an icon and return its id."""
    body = {"payload": {"kind": "feed", "title": "things", "icon": icon}}
    return (await client.post(ITEMS, json=body)).json()["id"]


async def test_a_widget_icon_is_served_by_id(client: AsyncClient, tmp_path: Path) -> None:
    """A widget can point at a picture, and it is fetched the way media is."""
    icon = tmp_path / "mark.png"
    icon.write_bytes(b"pretend-a-mark")
    item_id = await _add_feed(client, str(icon))
    response = await client.get(f"/api/v1/media/{item_id}/icon")
    assert response.status_code == 200
    assert response.content == b"pretend-a-mark"


async def test_a_named_icon_has_no_picture_to_serve(client: AsyncClient) -> None:
    """A glyph is drawn by the browser, so there is nothing here to stream."""
    item_id = await _add_feed(client, "github")
    assert (await client.get(f"/api/v1/media/{item_id}/icon")).status_code == 404


async def test_a_list_has_an_icon_of_its_own_as_well_as_its_entries(
    client: AsyncClient, tmp_path: Path
) -> None:
    """The widget's icon resolves like any other, so the same route serves it."""
    icon = tmp_path / "mark.png"
    icon.write_bytes(b"pretend-a-mark")
    body = {"payload": {"kind": "list", "title": "todo", "icon": str(icon)}}
    item_id = (await client.post(ITEMS, json=body)).json()["id"]
    assert (await client.get(f"/api/v1/media/{item_id}/icon")).content == b"pretend-a-mark"


async def test_a_list_entry_icon_is_served_by_its_place(
    client: AsyncClient, tmp_path: Path
) -> None:
    """A list carries an icon per line, so its index says which one is meant."""
    icon = tmp_path / "face.png"
    icon.write_bytes(b"pretend-a-face")
    items = ["plain line", {"title": "with a face", "icon": str(icon)}]
    body = {"payload": {"kind": "list", "items": items}}
    item_id = (await client.post(ITEMS, json=body)).json()["id"]
    response = await client.get(f"/api/v1/media/{item_id}/icon/1")
    assert response.status_code == 200
    assert response.content == b"pretend-a-face"
    assert (await client.get(f"/api/v1/media/{item_id}/icon/0")).status_code == 404
