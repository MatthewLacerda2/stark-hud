"""A flow on the wire: what survives, and what is refused in a sentence.

A flow is the one widget whose payload is a little graph, so the ways it can be
wrong are the ways a graph can be wrong — a name used twice, an arrow to nobody,
half the boxes placed and half not. Every one of them has to come back as a
sentence naming the offender rather than as a 500 or, worse, as a widget that
silently draws something nobody dictated. The caller is a model that cannot see
the television and has only that line to work out what it typed.
"""

from pathlib import Path

from httpx import AsyncClient

from repositories import board, store
from schemas.board import FlowPayload
from services import persistence

ITEMS = "/api/v1/board/items"

PIPELINE = {
    "kind": "flow",
    "title": "Deploy",
    "nodes": [
        {"id": "build", "text": "Build"},
        {"id": "test", "text": "Test", "shape": "ellipse"},
        {"id": "ship", "text": "Ship", "color": "success"},
    ],
    "links": [
        {"source": "build", "target": "test"},
        {"source": "test", "target": "ship", "label": "green"},
        {"source": "test", "target": "build", "label": "red", "curve": "s"},
    ],
}


def refusal(payload: dict) -> str:
    """The sentence a payload this wrong would be refused with."""
    try:
        FlowPayload.model_validate(payload)
    except ValueError as exc:
        return str(exc)
    raise AssertionError("that flow was accepted")


async def test_a_flow_keeps_its_boxes_and_arrows_through_the_api(client: AsyncClient) -> None:
    """Four boxes and the arrows between them are what the widget is."""
    response = await client.post(ITEMS, json={"payload": PIPELINE})
    assert response.status_code == 201
    drawn = response.json()["payload"]
    assert [n["id"] for n in drawn["nodes"]] == ["build", "test", "ship"]
    # A named colour resolves to the board's own variable, like every other colour.
    assert drawn["nodes"][2]["color"] == "var(--color-success)"
    # Nothing said where these sit, so nothing is stored about it: the line they
    # are drawn in is a reading the browser takes.
    assert drawn["nodes"][0]["x"] is None
    assert drawn["links"][2]["curve"] == "s"
    assert drawn["links"][0]["heads"] == "end"


async def test_a_link_to_a_node_that_is_not_there_is_a_sentence(client: AsyncClient) -> None:
    """Silently dropping the arrow would leave a diagram missing a step."""
    body = {
        "payload": {
            "kind": "flow",
            "nodes": [{"id": "build", "text": "Build"}],
            "links": [{"source": "build", "target": "deploy"}],
        }
    }
    response = await client.post(ITEMS, json=body)
    assert response.status_code == 422
    assert "'deploy'" in response.text


def test_the_sentence_names_the_end_that_was_wrong() -> None:
    """Which of the two ends is wrong is the whole of what the caller needs."""
    said = refusal(
        {
            "kind": "flow",
            "nodes": [{"id": "build", "text": "Build"}],
            "links": [{"source": "clone", "target": "build"}],
        }
    )
    assert "source is 'clone'" in said
    assert "'build'" in said


def test_two_nodes_with_one_name_are_refused_naming_it() -> None:
    """A link names a node, so two of them called 'build' makes that ambiguous."""
    said = refusal(
        {
            "kind": "flow",
            "nodes": [{"id": "build", "text": "Build"}, {"id": "build", "text": "Rebuild"}],
            "links": [],
        }
    )
    assert "'build'" in said


def test_a_half_placed_flow_is_refused_naming_both_sides() -> None:
    """There is no honest way to fit the rest around what was given."""
    said = refusal(
        {
            "kind": "flow",
            "nodes": [
                {"id": "build", "text": "Build", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
                {"id": "test", "text": "Test"},
            ],
            "links": [],
        }
    )
    assert "'build'" in said
    assert "'test'" in said


def test_a_box_that_gives_only_some_of_its_four_numbers_is_refused() -> None:
    """Half a rectangle is a layout engine with a special case in it."""
    said = refusal(
        {
            "kind": "flow",
            "nodes": [{"id": "build", "text": "Build", "x": 0.1, "y": 0.1}],
            "links": [],
        }
    )
    assert "'build'" in said
    assert "w" in said and "h" in said


def test_a_far_edge_outside_the_widget_is_refused_not_clipped() -> None:
    """This widget does not scroll, so anything past its edge is invisible."""
    said = refusal(
        {
            "kind": "flow",
            "nodes": [{"id": "build", "text": "Build", "x": 0.8, "y": 0.1, "w": 0.4, "h": 0.2}],
            "links": [],
        }
    )
    assert "'build'" in said
    assert "1.2" in said


def test_a_near_edge_outside_the_widget_is_refused_too() -> None:
    """Unlike scorsese, nothing here comes in from off-screen: there is no off."""
    said = refusal(
        {
            "kind": "flow",
            "nodes": [{"id": "build", "text": "Build", "x": 0.1, "y": -0.2, "w": 0.2, "h": 0.2}],
            "links": [],
        }
    )
    assert "'build'" in said


def test_a_loop_back_into_the_same_node_is_refused() -> None:
    """A self-link is a zero-length arrow, which draws nothing and says nothing."""
    said = refusal(
        {
            "kind": "flow",
            "nodes": [{"id": "build", "text": "Build"}],
            "links": [{"source": "build", "target": "build"}],
        }
    )
    assert "'build'" in said


def test_the_same_arrow_twice_is_refused() -> None:
    """The second would be laid exactly over the first and be invisible."""
    said = refusal(
        {
            "kind": "flow",
            "nodes": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "links": [{"source": "a", "target": "b"}, {"source": "a", "target": "b", "label": "x"}],
        }
    )
    assert "'a'" in said and "'b'" in said


def test_an_arrow_each_way_between_two_boxes_is_allowed() -> None:
    """a leads to b and b leads back to a is a cycle, not a duplicate."""
    FlowPayload.model_validate(
        {
            "kind": "flow",
            "nodes": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "links": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
        }
    )


def test_a_flow_comes_back_off_the_disk_intact(tmp_path: Path, monkeypatch) -> None:
    """The board is restored from a file, so a diagram has to survive a restart."""
    monkeypatch.setattr(store, "path", lambda: tmp_path / "board.hud")
    payload = FlowPayload.model_validate(PIPELINE)
    item = board.add(payload, 0, 0, 8, 6, None, False, key="deploy")

    assert persistence.save()
    board.clear()
    persistence.restore()

    restored = board.get(item.id)
    assert isinstance(restored.payload, FlowPayload)
    assert [n.id for n in restored.payload.nodes] == ["build", "test", "ship"]
    assert restored.payload.links[1].label == "green"
    assert restored.payload.nodes[1].shape == "ellipse"
