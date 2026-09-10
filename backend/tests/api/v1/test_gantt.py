"""A gantt on the wire and on disk: what survives, and what is refused.

The whole design rests on the payload carrying instants rather than readings, so
what these check is that the instants make it there and back unchanged — through
the API, and through the ``.hud`` file the board is restored from. A datetime
that came back as a string, or a bar that lost its colour on the way to disk,
would leave the widget drawing a plan nobody wrote.
"""

from datetime import datetime
from pathlib import Path

from httpx import AsyncClient

from repositories import board, store
from schemas.board import GanttPayload
from services import persistence

ITEMS = "/api/v1/board/items"

EVENING = {
    "kind": "gantt",
    "title": "Tonight",
    "rows": [
        {
            "name": "Kitchen",
            "bars": [
                {"title": "sauce", "start": "2026-09-04T18:00", "end": "2026-09-04T18:45"},
                {"title": "bake", "start": "2026-09-04T18:45", "end": "2026-09-04T19:30"},
            ],
        },
        {
            "name": "Laundry",
            "bars": [
                {
                    "title": "wash",
                    "start": "2026-09-04T18:30",
                    "end": "2026-09-04T19:30",
                    "color": "chart-3",
                }
            ],
        },
    ],
}


async def test_a_gantt_keeps_its_instants_through_the_api(client: AsyncClient) -> None:
    """Two rows overlapping in time is the thing this widget exists to say."""
    response = await client.post(ITEMS, json={"payload": EVENING})
    assert response.status_code == 201
    rows = response.json()["payload"]["rows"]
    assert [row["name"] for row in rows] == ["Kitchen", "Laundry"]
    assert rows[0]["bars"][0]["start"].startswith("2026-09-04T18:00")
    # A named colour resolves to the board's own variable, like every other colour.
    assert rows[1]["bars"][0]["color"] == "var(--color-chart-3)"


async def test_a_bar_with_no_width_is_refused(client: AsyncClient) -> None:
    """Width is the only thing here carrying duration, so a bar needs both ends."""
    bar = {"title": "sauce", "start": "2026-09-04T18:00", "end": "2026-09-04T18:00"}
    body = {"payload": {"kind": "gantt", "rows": [{"name": "Kitchen", "bars": [bar]}]}}
    assert (await client.post(ITEMS, json=body)).status_code == 422


async def test_a_bar_missing_its_end_is_refused(client: AsyncClient) -> None:
    """A span with no end is a countdown entry, and belongs in that widget."""
    body = {
        "payload": {
            "kind": "gantt",
            "rows": [
                {"name": "Kitchen", "bars": [{"title": "sauce", "start": "2026-09-04T18:00"}]}
            ],
        }
    }
    assert (await client.post(ITEMS, json=body)).status_code == 422


async def test_half_a_timezone_is_a_sentence_and_not_a_crash(client: AsyncClient) -> None:
    """Comparing an aware datetime with a naive one raises; the caller gets a 422."""
    bar = {"title": "sauce", "start": "2026-09-04T18:00", "end": "2026-09-04T18:45Z"}
    body = {"payload": {"kind": "gantt", "rows": [{"name": "Kitchen", "bars": [bar]}]}}
    response = await client.post(ITEMS, json=body)
    assert response.status_code == 422
    assert "timezone" in response.text


def test_a_gantt_comes_back_off_the_disk_intact(tmp_path: Path, monkeypatch) -> None:
    """The board is restored from a file, so an evening has to survive a restart."""
    monkeypatch.setattr(store, "path", lambda: tmp_path / "board.hud")
    payload = GanttPayload.model_validate(EVENING)
    item = board.add(payload, 0, 0, 12, 6, None, False, key="tonight")

    assert persistence.save()
    board.clear()
    persistence.restore()

    restored = board.get(item.id)
    assert isinstance(restored.payload, GanttPayload)
    bar = restored.payload.rows[0].bars[0]
    # A datetime, not the string it was written as: the browser is handed instants.
    assert bar.start == datetime(2026, 9, 4, 18, 0)
    assert restored.payload.rows[1].bars[0].color == "var(--color-chart-3)"
