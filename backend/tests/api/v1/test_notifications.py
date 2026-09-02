"""The inbox: one place several writers announce into."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from repositories import notifications as repo

URL = "/api/v1/notifications"


async def test_announcing_and_reading_back(client: AsyncClient) -> None:
    """A notification comes back with an id and a time it was made."""
    body = {"title": "deploy done", "body": "12 tests", "icon": "rocket", "source": "ci"}
    created = (await client.post(URL, json=body)).json()
    assert created["id"] and created["created_at"]

    inbox = (await client.get(URL)).json()
    assert [n["title"] for n in inbox["notifications"]] == ["deploy done"]
    assert inbox["retention_hours"] == 48


async def test_newest_first(client: AsyncClient) -> None:
    """The inbox reads like a phone's: most recent at the top."""
    for title in ("first", "second", "third"):
        await client.post(URL, json={"title": title})
    inbox = (await client.get(URL)).json()
    assert [n["title"] for n in inbox["notifications"]] == ["third", "second", "first"]


async def test_an_unknown_icon_is_refused_with_the_list(client: AsyncClient) -> None:
    """A typo would draw nothing, so it is rejected while someone can fix it."""
    response = await client.post(URL, json={"title": "x", "icon": "definitely-not-an-icon"})
    assert response.status_code == 422
    assert "bell" in response.json()["detail"]


async def test_a_path_that_is_not_there_is_refused(client: AsyncClient) -> None:
    """An icon path is checked when it is set, like the background."""
    assert (await client.post(URL, json={"title": "x", "icon": "/no/such.png"})).status_code == 422


async def test_anything_past_the_window_drops_out(client: AsyncClient) -> None:
    """48 hours is the whole retention policy; there is no other cleanup."""
    await client.post(URL, json={"title": "recent"})
    stale = repo._notifications[0].model_copy(  # noqa: SLF001 - reaching in to age one
        update={
            "id": "old",
            "title": "ancient",
            "created_at": datetime.now(UTC) - timedelta(hours=49),
        }
    )
    repo._notifications.append(stale)  # noqa: SLF001

    inbox = (await client.get(URL)).json()
    assert [n["title"] for n in inbox["notifications"]] == ["recent"]


async def test_search_matches_title_body_or_source(client: AsyncClient) -> None:
    """One substring across all three fields, so a caller does not pick a column."""
    await client.post(URL, json={"title": "deploy done", "source": "ci"})
    await client.post(URL, json={"title": "tests green", "body": "after the deploy"})
    await client.post(URL, json={"title": "unrelated", "source": "trm"})

    assert len(repo.search("deploy")) == 2
    assert [n.title for n in repo.search("TRM")] == ["unrelated"]
    assert repo.search("nothing like this") == []


async def test_the_claude_mark_is_an_icon(client: AsyncClient) -> None:
    """A session announcing itself can say which one it is."""
    response = await client.post(URL, json={"title": "done", "icon": "claude"})
    assert response.status_code == 201
    assert response.json()["icon"] == "claude"


async def test_an_svg_icon_is_stored_sanitised(client: AsyncClient) -> None:
    """The inbox takes markup like every other icon, and keeps only what draws."""
    markup = '<svg viewBox="0 0 24 24"><script>alert(1)</script><path d="M1 1"/></svg>'
    response = await client.post(URL, json={"title": "done", "icon": markup})

    assert response.status_code == 201
    assert "script" not in response.json()["icon"]
    assert '<path d="M1 1"' in response.json()["icon"]


async def test_svg_that_draws_nothing_is_refused(client: AsyncClient) -> None:
    """Markup emptied by the allowlist would show as no icon at all."""
    response = await client.post(URL, json={"title": "x", "icon": "<svg><title>x</title></svg>"})

    assert response.status_code == 422
    assert "nothing this board draws" in response.json()["detail"]
