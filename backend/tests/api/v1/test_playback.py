"""The one flow on this board that runs browser to server.

Everything else is written by whoever drives the board and drawn by the TV. Only
the TV knows whether a file decoded, so what it says has to land somewhere a
session can read — on the item, where the widget's own owner cannot overwrite
it, and where a finished track also moves the queue on.
"""

from pathlib import Path

from httpx import AsyncClient

ITEMS = "/api/v1/board/items"
TRACKS = ["/music/one.mp3", "/music/two.mp3", "/music/three.mp3"]


def _queue(loop: bool = False, index: int = 0) -> dict:
    """The body that puts a three-track player on the board."""
    return {
        "payload": {
            "kind": "media",
            "tracks": [{"path": p} for p in TRACKS],
            "loop": loop,
            "index": index,
        }
    }


async def _player(client: AsyncClient, loop: bool = False, index: int = 0) -> str:
    """Create a media widget and return its id."""
    return (await client.post(ITEMS, json=_queue(loop, index))).json()["id"]


async def _say(client: AsyncClient, item_id: str, **report: object) -> dict:
    """Report playback the way the page does, and read the item back."""
    response = await client.post(f"{ITEMS}/{item_id}/playback", json=report)
    assert response.status_code == 200, response.text
    return response.json()


async def test_what_the_browser_says_lands_on_the_item(client: AsyncClient) -> None:
    """It comes back on the item, so list_items shows it without being asked."""
    item_id = await _player(client)
    item = await _say(client, item_id, state="playing", track=0)
    assert item["playback"]["state"] == "playing"
    # The name is copied in so a reader learns what is playing without counting.
    assert item["playback"]["title"] == "one"
    listed = (await client.get(ITEMS)).json()[0]
    assert listed["playback"]["state"] == "playing"


async def test_a_failure_says_why_instead_of_looking_like_silence(client: AsyncClient) -> None:
    """A codec the browser will not take is the case this whole flow exists for."""
    item_id = await _player(client)
    item = await _say(client, item_id, state="failed", track=0, error="MEDIA_ERR_DECODE")
    assert item["playback"]["error"] == "MEDIA_ERR_DECODE"
    # It does not move on: a queue that walked past it would overwrite the reason.
    assert item["payload"]["index"] == 0


async def test_it_survives_the_payload_being_rewritten(client: AsyncClient) -> None:
    """A payload belongs to whoever writes the widget; this is not theirs to erase."""
    created = (await client.put(f"{ITEMS}/by-key/album", json=_queue())).json()
    await _say(client, created["id"], state="playing", track=0)
    rewritten = (await client.put(f"{ITEMS}/by-key/album", json=_queue(loop=True))).json()
    assert rewritten["payload"]["loop"] is True
    assert rewritten["playback"]["state"] == "playing"


async def test_a_finished_track_moves_the_queue_on(client: AsyncClient) -> None:
    """This is how an album plays itself through with nobody in the room."""
    item_id = await _player(client)
    assert (await _say(client, item_id, state="ended", track=0))["payload"]["index"] == 1
    assert (await _say(client, item_id, state="ended", track=1))["payload"]["index"] == 2


async def test_the_last_track_stops_or_wraps_as_the_widget_was_told(client: AsyncClient) -> None:
    """Loop is the whole difference between an album and an album on repeat."""
    plain = await _player(client, index=2)
    ended = await _say(client, plain, state="ended", track=2)
    assert (ended["payload"]["index"], ended["payload"]["playing"]) == (0, False)

    looping = await _player(client, loop=True, index=2)
    wrapped = await _say(client, looping, state="ended", track=2)
    assert (wrapped["payload"]["index"], wrapped["payload"]["playing"]) == (0, True)


async def test_a_late_report_cannot_skip_a_track(client: AsyncClient) -> None:
    """A message about a track we already left must not move the one after it."""
    item_id = await _player(client)
    await _say(client, item_id, state="ended", track=0)
    assert (await _say(client, item_id, state="ended", track=0))["payload"]["index"] == 1


async def test_a_widget_that_plays_nothing_has_nothing_to_report(client: AsyncClient) -> None:
    """Reporting playback on a note is a client bug, and says so."""
    note = (await client.post(ITEMS, json={"payload": {"kind": "note", "text": "x"}})).json()
    response = await client.post(f"{ITEMS}/{note['id']}/playback", json={"state": "playing"})
    assert response.status_code == 404
    assert "plays nothing" in response.json()["detail"]


async def test_the_queue_reaches_the_browser_by_id_and_index(
    client: AsyncClient, tmp_path: Path
) -> None:
    """The apostrophe and the spaces never leave the server: the URL is an id."""
    folder = tmp_path / "AC DC - Greatest Hell's Hits" / "CD1"
    folder.mkdir(parents=True)
    (folder / "01 - Highway to Hell.mp3").write_bytes(b"id3-and-then-some")
    (folder / "AlbumArt_Large.jpg").write_bytes(b"jpeg")
    body = {
        "payload": {"kind": "media", "tracks": [{"path": str(folder / "01 - Highway to Hell.mp3")}]}
    }
    item_id = (await client.post(ITEMS, json=body)).json()["id"]

    assert (await client.get(f"/api/v1/media/{item_id}/track/0")).content == b"id3-and-then-some"
    assert (await client.get(f"/api/v1/media/{item_id}/track/0/art")).content == b"jpeg"
    assert (await client.get(f"/api/v1/media/{item_id}/track/9")).status_code == 404


async def test_a_youtube_video_moves_the_queue_on_like_any_other_track(
    client: AsyncClient,
) -> None:
    """The same report, the same rule: where a track came from changes nothing here."""
    mixed = {
        "payload": {
            "kind": "media",
            "tracks": [
                {"youtube": "https://www.youtube.com/watch?v=QgH9sr7G13Q"},
                {"path": "/music/one.mp3"},
            ],
        }
    }
    created = (await client.post(ITEMS, json=mixed)).json()
    item_id = created["id"]
    # Whatever shape the link arrived as, what is stored is the id.
    assert created["payload"]["tracks"][0]["youtube"] == "QgH9sr7G13Q"

    ended = await _say(client, item_id, state="ended", track=0)
    assert ended["payload"]["index"] == 1
    # And there is nothing on this machine to stream for it.
    assert (await client.get(f"/api/v1/media/{item_id}/track/0")).status_code == 404


async def test_a_video_nobody_may_embed_says_so_in_words(client: AsyncClient) -> None:
    """The failure this whole flow exists for: it plays nowhere but youtube.com."""
    body = {"payload": {"kind": "media", "tracks": [{"youtube": "QgH9sr7G13Q"}]}}
    item_id = (await client.post(ITEMS, json=body)).json()["id"]
    refusal = "the owner does not allow this video to be played outside YouTube"

    item = await _say(client, item_id, state="failed", track=0, error=refusal)
    assert item["playback"]["error"] == refusal
    # It stays on the track it could not play, so the reason is still there to read.
    assert item["payload"]["index"] == 0
