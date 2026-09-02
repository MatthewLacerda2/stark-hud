"""Item lifecycle: validation, updates, parenting, and clearing."""

from httpx import AsyncClient

NOTE = {"payload": {"kind": "note", "text": "hello"}}
ITEMS = "/api/v1/board/items"


async def test_unknown_kind_is_rejected(client: AsyncClient) -> None:
    """The discriminated union refuses a payload kind that does not exist."""
    response = await client.post(ITEMS, json={"payload": {"kind": "hologram", "text": "x"}})
    assert response.status_code == 422


async def test_chart_requires_its_axis(client: AsyncClient) -> None:
    """A chart without x_key is a client bug, not a defaulted value."""
    body = {"payload": {"kind": "chart", "chart": "bar", "series": ["a"], "data": []}}
    assert (await client.post(ITEMS, json=body)).status_code == 422


async def test_update_moves_and_rewrites_payload(client: AsyncClient) -> None:
    """PATCH applies geometry and payload changes together."""
    item = (await client.post(ITEMS, json=NOTE)).json()
    patch = {"x": 8, "y": 6, "payload": {"kind": "note", "text": "changed"}}
    updated = (await client.patch(f"{ITEMS}/{item['id']}", json=patch)).json()
    assert (updated["x"], updated["y"]) == (8, 6)
    assert updated["payload"]["text"] == "changed"


async def test_removing_a_box_orphans_its_children(client: AsyncClient) -> None:
    """Losing a container must never silently delete its content."""
    box = (await client.post(ITEMS, json={"payload": {"kind": "box", "label": "group"}})).json()
    child = (await client.post(ITEMS, json={**NOTE, "parent_id": box["id"]})).json()
    await client.delete(f"{ITEMS}/{box['id']}")
    survivors = (await client.get(ITEMS)).json()
    assert [i["id"] for i in survivors] == [child["id"]]
    assert survivors[0]["parent_id"] is None


async def test_clear_reports_how_many_it_dropped(client: AsyncClient) -> None:
    """DELETE on the collection empties the board and says how much it removed."""
    for _ in range(3):
        await client.post(ITEMS, json=NOTE)
    assert (await client.delete(ITEMS)).json() == {"removed": 3}
    assert (await client.get(ITEMS)).json() == []


async def test_missing_item_is_404(client: AsyncClient) -> None:
    """An unknown id is not found, not a server error."""
    assert (await client.patch(f"{ITEMS}/nope", json={"x": 0})).status_code == 404


async def test_a_list_holds_plain_lines_and_richer_ones_together(client: AsyncClient) -> None:
    """Strings are what a script prints; a line a person wrote may want more."""
    items = ["17:02 up", {"title": "deploy", "body": "waiting on review", "icon": "rocket"}]
    response = await client.post(ITEMS, json={"payload": {"kind": "list", "items": items}})
    assert response.status_code == 201
    stored = response.json()["payload"]["items"]
    assert stored[0] == "17:02 up"
    assert stored[1]["body"] == "waiting on review"


async def test_a_list_entry_icon_must_be_a_name_or_a_path(client: AsyncClient) -> None:
    """A typo would draw nothing and explain nothing, so it is refused here."""
    body = {"payload": {"kind": "list", "items": [{"title": "x", "icon": "rockit"}]}}
    assert (await client.post(ITEMS, json=body)).status_code == 422


async def test_a_description_survives_a_round_trip(client: AsyncClient) -> None:
    """A note written at creation is read back, changed, and taken off again."""
    body = {**NOTE, "description": "the standup board; clear it every Monday"}
    item = (await client.post(ITEMS, json=body)).json()
    assert item["description"] == "the standup board; clear it every Monday"

    listed = (await client.get(ITEMS)).json()[0]
    assert listed["description"] == item["description"]

    url = f"{ITEMS}/{item['id']}"
    changed = (await client.patch(url, json={"description": "now waiting on the API key"})).json()
    assert changed["description"] == "now waiting on the API key"

    # Everything else on an update treats null as untouched, so an empty string
    # is the only way back to no note at all.
    assert (await client.patch(url, json={"x": 4})).json()["description"] == changed["description"]
    assert (await client.patch(url, json={"description": ""})).json()["description"] is None
