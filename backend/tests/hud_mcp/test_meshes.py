"""Colouring a model, and setting a colour running through it."""

import pytest
from mcp.server.mcpserver import MCPServer

from core.hub import hub
from hud_mcp.server import build_server
from repositories import board as repo
from schemas.board import MeshPayload


@pytest.fixture
def server() -> MCPServer:
    """A server with every tool registered."""
    return build_server()


async def call(server: MCPServer, name: str, **args: object) -> str:
    """Call a tool and return its text, the way an agent would see it."""
    return (await server.call_tool(name, args)).content[0].text


async def a_mesh(server: MCPServer) -> str:
    """Put a mesh widget on the board and give back its id."""
    said = await call(server, "add_mesh", path="/models/thing.obj", w=6, h=6)
    return said.split("mesh ")[1].split(" ")[0]


def payload(item_id: str) -> MeshPayload:
    """The mesh payload now on the board."""
    item = repo.get(item_id)
    assert item is not None
    assert isinstance(item.payload, MeshPayload)
    return item.payload


async def test_a_new_model_has_no_colours_of_its_own(server: MCPServer) -> None:
    """A mesh starts in the widget's own ink, like every other widget."""
    found = payload(await a_mesh(server))
    assert found.colors is None
    assert found.wave is None


async def test_parts_can_be_painted_by_name_and_by_glob(server: MCPServer) -> None:
    """A glob is what stops seven encoder rings being seven arguments."""
    item_id = await a_mesh(server)
    await call(server, "color_mesh", target=item_id, colors={"encoder_*": "chart-2"})
    assert payload(item_id).colors == {"encoder_*": "var(--color-chart-2)"}


async def test_a_wave_starts_from_a_ramp_when_none_is_named(server: MCPServer) -> None:
    """Switching it on should not require knowing what to switch it on to."""
    item_id = await a_mesh(server)
    await call(server, "color_mesh", target=item_id, wave="stack")
    wave = payload(item_id).wave
    assert wave is not None
    assert wave.mode == "stack"
    assert len(wave.colors) >= 2


async def test_adjusting_a_wave_keeps_the_ramp_somebody_chose(server: MCPServer) -> None:
    """Turning the speed up must not quietly throw the colours away."""
    item_id = await a_mesh(server)
    await call(server, "color_mesh", target=item_id, wave="loop", wave_colors=["white", "accent"])
    await call(server, "color_mesh", target=item_id, wave_seconds=3)
    wave = payload(item_id).wave
    assert wave is not None
    assert wave.seconds == 3
    assert wave.mode == "loop"
    assert len(wave.colors) == 2


async def test_a_wave_can_be_switched_off(server: MCPServer) -> None:
    """And the part colours beside it are left alone."""
    item_id = await a_mesh(server)
    await call(server, "color_mesh", target=item_id, colors={"head": "accent"}, wave="stack")
    await call(server, "color_mesh", target=item_id, wave="off")
    assert payload(item_id).wave is None
    assert payload(item_id).colors == {"head": "var(--color-accent)"}


async def test_an_empty_set_of_colours_clears_them(server: MCPServer) -> None:
    """Written whole, like a chart: nothing means back to the widget's own ink."""
    item_id = await a_mesh(server)
    await call(server, "color_mesh", target=item_id, colors={"head": "accent"})
    await call(server, "color_mesh", target=item_id, colors={})
    assert payload(item_id).colors is None


async def test_a_colour_that_would_draw_nothing_is_refused(server: MCPServer) -> None:
    """The same rule every other widget's colours follow: say so, don't drop it."""
    item_id = await a_mesh(server)
    said = await call(server, "color_mesh", target=item_id, colors={"head": "acent"})
    assert "Not set" in said or "not a colour" in said
    assert payload(item_id).colors is None


async def test_an_unknown_mode_is_refused(server: MCPServer) -> None:
    """A typo must not leave a wave that never runs."""
    item_id = await a_mesh(server)
    said = await call(server, "color_mesh", target=item_id, wave="sideways")
    assert "Not set" in said
    assert payload(item_id).wave is None


async def test_saying_nothing_changes_nothing(server: MCPServer) -> None:
    """And says which words would have worked."""
    said = await call(server, "color_mesh", target=await a_mesh(server))
    assert "Nothing to set" in said


async def test_colouring_something_that_is_not_a_mesh(server: MCPServer) -> None:
    """A readable sentence rather than an exception, like every tool here."""
    note = await call(server, "add_note", text="hello")
    said = await call(server, "color_mesh", target=note.split("note ")[1].split(" ")[0])
    assert "No mesh widget" in said


class Listener:
    """A socket that keeps what it was sent, so a broadcast can be read back."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def accept(self) -> None:
        return None

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


async def test_reloading_tells_the_boards_without_changing_the_widget(
    server: MCPServer,
) -> None:
    """The whole point: the file moved, the widget did not.

    An `item.updated` here would rewrite the board file and make every other
    client redraw a widget whose payload is identical — so this is its own
    ephemeral event, the shape `item.waking` already uses.
    """
    item_id = await a_mesh(server)
    before = repo.get(item_id)
    socket = Listener()
    await hub.connect(socket)
    try:
        said = await call(server, "reload_mesh", target=item_id)
    finally:
        await hub.disconnect(socket)

    assert "/models/thing.obj" in said
    assert socket.sent == [{"event": "mesh.reloaded", "data": {"id": item_id}}]
    assert repo.get(item_id) == before


async def test_reloading_something_that_is_not_a_mesh(server: MCPServer) -> None:
    """A readable sentence rather than an exception, like every tool here."""
    note = await call(server, "add_note", text="hello")
    said = await call(server, "reload_mesh", target=note.split("note ")[1].split(" ")[0])
    assert "No mesh widget" in said
