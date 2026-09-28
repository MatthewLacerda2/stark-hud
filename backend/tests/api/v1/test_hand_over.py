"""A track handed to a player by a person, from the button on the widget.

The route replaces the queue and plays what it was given. These pin the three
things the button relies on: a YouTube link is read by the server and a link to
anywhere else is refused with a sentence the page can show as it is; a file is
built into a track the way ``set_media_queue`` builds one, stamp and all; and
whatever the widget was doing before is forgotten rather than carried over.
"""

from pathlib import Path

from httpx import AsyncClient

ITEMS = "/api/v1/board/items"
VIDEO = "QgH9sr7G13Q"


async def _player(client: AsyncClient) -> str:
    """A paused player somewhere in the middle of an album, and its id."""
    tracks = [{"path": f"/music/{n}.mp3"} for n in ("one", "two", "three")]
    payload = {"kind": "media", "tracks": tracks, "index": 2, "playing": False}
    payload |= {"seconds": 95.0, "title": "Some Album"}
    created = await client.post(ITEMS, json={"payload": payload})
    return created.json()["id"]


async def _hand(client: AsyncClient, item_id: str, **track: str):
    """Hand the player one track, the way the button does."""
    return await client.put(f"{ITEMS}/{item_id}/queue", json=track)


async def test_a_youtube_link_replaces_the_queue_and_plays(client: AsyncClient) -> None:
    """Whatever shape was pasted, the id is kept and the old queue is gone."""
    item_id = await _player(client)
    handed = await _hand(client, item_id, youtube=f"https://youtu.be/{VIDEO}?si=share")
    assert handed.status_code == 200, handed.text
    payload = handed.json()["payload"]
    assert [t["youtube"] for t in payload["tracks"]] == [VIDEO]
    # Where the album had got to, and what it was called, were about the album.
    assert (payload["index"], payload["seconds"], payload["title"]) == (0, 0.0, None)
    assert payload["playing"] is True


async def test_a_link_that_is_not_youtube_is_refused_in_a_sentence(
    client: AsyncClient,
) -> None:
    """Refused as not YouTube — never taken for a file whose name is a URL."""
    item_id = await _player(client)
    refused = await _hand(client, item_id, youtube="https://example.com/film.mp4")
    assert refused.status_code == 422
    assert refused.json()["detail"] == "'https://example.com/film.mp4' is not a YouTube link"
    unchanged = (await client.get(ITEMS)).json()[0]["payload"]
    assert len(unchanged["tracks"]) == 3


async def test_a_youtube_link_with_no_video_in_it_says_so(client: AsyncClient) -> None:
    """The parser's own sentence comes back, not a generic one."""
    item_id = await _player(client)
    refused = await _hand(client, item_id, youtube="https://www.youtube.com/feed/library")
    assert refused.status_code == 422
    assert "no video id" in refused.json()["detail"]


async def test_two_files_in_a_row_are_two_urls(client: AsyncClient, tmp_path: Path) -> None:
    """The reason this is a route and not a PATCH: each file is stamped.

    Both land at track 0 of the same widget. Without a stamp that is one URL,
    and the browser would go on playing the first file after the second arrived.
    """
    item_id = await _player(client)
    stamps = []
    for name in ("first.mp4", "second.mp4"):
        (tmp_path / name).write_bytes(name.encode())
        handed = await _hand(client, item_id, path=str(tmp_path / name))
        assert handed.status_code == 200, handed.text
        track = handed.json()["payload"]["tracks"][0]
        assert (track["kind"], track["title"]) == ("video", Path(name).stem)
        stamps.append(track["stamp"])
    assert stamps[0] and stamps[1] and stamps[0] != stamps[1]


async def test_only_a_player_takes_a_track(client: AsyncClient) -> None:
    """A missing widget and a widget that plays nothing are both a 404."""
    note = await client.post(ITEMS, json={"payload": {"kind": "note", "text": "hi"}})
    refused = await _hand(client, note.json()["id"], youtube=VIDEO)
    assert refused.status_code == 404
    assert "plays nothing" in refused.json()["detail"]
    assert (await _hand(client, "nope", youtube=VIDEO)).status_code == 404


async def test_a_body_naming_both_or_neither_is_refused(client: AsyncClient) -> None:
    """One track, from one place."""
    item_id = await _player(client)
    assert (await _hand(client, item_id)).status_code == 422
    both = await _hand(client, item_id, youtube=VIDEO, path="/music/one.mp3")
    assert both.status_code == 422
