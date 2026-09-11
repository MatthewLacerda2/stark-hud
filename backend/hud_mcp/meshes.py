"""The MCP tools for the mesh widget: put a model on the board, and turn it.

Two tools, split the way the media widget's are. ``add_mesh`` says which model,
and after that the file never changes; ``set_mesh`` is how the thing is driven —
faster, slower, tilted, pulled apart — because a model sitting on the television
is watched and adjusted rather than rewritten.

Only OBJ is read here. Everything else on this machine — FBX, glTF, a .blend —
goes through ``tools/mesh/convert.py`` first, which drives Blender and writes an
OBJ beside whatever it was given.
"""

from mcp.server.mcpserver import MCPServer

from core.hub import hub
from hud_mcp.common import add, find
from schemas.board import ItemRead, ItemUpdate, MeshPayload
from services import board as service
from services.board import SlotTakenError


def register(server: MCPServer) -> None:
    """Attach the mesh tools to the server."""

    def _mesh(target: str) -> tuple[ItemRead, MeshPayload] | None:
        """The widget with that id or key, when it is a mesh and not something else."""
        item = find(target)
        if item is None or not isinstance(item.payload, MeshPayload):
            return None
        return item, item.payload

    @server.tool()
    async def add_mesh(
        path: str,
        spin: float = 0.08,
        tilt: float = 16.0,
        explode: float = 0.0,
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
        parent_id: str | None = None,
        description: str | None = None,
    ) -> str:
        """Show a 3D model as a turning wireframe, the way a hologram reads.

        `path` is an OBJ file on the machine running the board. Anything else —
        FBX, glTF, GLB, STL, PLY, or a .blend — is converted first:

            python tools/mesh/convert.py ~/Downloads/helmet.fbx

        which writes `helmet.obj` beside it and prints the path to pass here.

        Only the mesh is read. Materials, textures, normals and any animation in
        the file are dropped, because the widget draws edges in one colour and
        there is nothing for them to be. The model is centred and scaled to fit
        the widget on the way in, so a model saved in millimetres and one saved
        in metres both arrive the right size and neither needs a scale argument.

        `spin` is turns per second and the default is slow on purpose — once
        every twelve seconds reads as an object on a turntable, while anything
        brisk reads as a loading spinner. Negative turns the other way; zero
        holds it still.

        `tilt` is how far above the model the camera sits, in degrees. `explode`
        pulls the model's parts apart along the line from its middle, where 0 is
        assembled and 1 is a full model-width of separation — and it only does
        anything for a file saved as several named objects, since a model
        exported as one lump has one part and nothing to come apart from.

        Give it room. A wireframe read from a sofa wants 6 by 6 or more; below
        about 4 by 4 the lines converge and it stops being a shape.

        This is the one widget that removes itself when its file goes missing,
        rather than showing a placeholder. If the model is on a drive that is not
        always mounted, expect the widget to be gone after a reboot — a line in
        the inbox says which file it was.
        """
        payload = MeshPayload(path=path, spin=spin, tilt=tilt, explode=explode)
        return await add(payload, x, y, w, h, parent_id, description=description)

    @server.tool()
    async def set_mesh(
        target: str,
        spin: float | None = None,
        tilt: float | None = None,
        explode: float | None = None,
    ) -> str:
        """Change how a model turns, leans, or comes apart.

        Everything is optional and only what you pass moves, the way set_style
        and set_media_mode work. `target` is the widget's id or its key.

        There is no `path` here on purpose: which model a widget shows is what
        the widget *is*, and swapping it would leave the description, the key and
        the size of one model attached to another. Remove it and add the new one.
        """
        found = _mesh(target)
        if found is None:
            return f"No mesh widget {target!r}. Call list_items to see what is there."
        item, model = found
        asked = {"spin": spin, "tilt": tilt, "explode": explode}
        given = {name: value for name, value in asked.items() if value is not None}
        if not given:
            return "Nothing to set: pass at least one of spin, tilt or explode"
        try:
            payload = model.model_copy(update=given)
            # Validated rather than trusted: model_copy does not run the field
            # bounds, so a spin of 400 would sit in the payload and reach the
            # browser as a model turning too fast to be a model.
            payload = MeshPayload.model_validate(payload.model_dump())
            updated = service.update(item, ItemUpdate(payload=payload))
        except ValueError as exc:
            return f"Not set: {exc}"
        except SlotTakenError as exc:
            return f"Not set: {exc}"
        await hub.broadcast("item.updated", updated.model_dump(mode="json"))
        said = ", ".join(f"{name}={value:g}" for name, value in given.items())
        return f"Set {said} on {item.id}"
