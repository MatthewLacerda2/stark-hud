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
from schemas.board import ItemRead, ItemUpdate, MeshPayload, MeshWave
from services import board as service
from services.board import SlotTakenError

# What a wave runs through when it is switched on without a ramp being named.
# White through blue to red, and back round through red to white: the colours a
# heads-up display has always used for "cold, working, hot", on a board whose
# own palette supplies the last two.
DEFAULT_RAMP = ("white", "info", "destructive")


def register(server: MCPServer) -> None:
    """Attach the mesh tools to the server."""

    def _mesh(target: str) -> tuple[ItemRead, MeshPayload] | None:
        """The widget with that id or key, when it is a mesh and not something else."""
        item = find(target)
        if item is None or not isinstance(item.payload, MeshPayload):
            return None
        return item, item.payload

    async def _write(item: ItemRead, payload: MeshPayload, said: str) -> str:
        """Validate the new payload, store it, and tell every board."""
        try:
            # Validated rather than trusted: model_copy does not run the field
            # bounds, so a spin of 400 would sit in the payload and reach the
            # browser as a model turning too fast to be a model.
            checked = MeshPayload.model_validate(payload.model_dump())
            updated = service.update(item, ItemUpdate(payload=checked))
        except ValueError as exc:
            return f"Not set: {exc}"
        except SlotTakenError as exc:
            return f"Not set: {exc}"
        await hub.broadcast("item.updated", updated.model_dump(mode="json"))
        return f"Set {said} on {item.id}"

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

        Block it out, put it up, and then make it good. A model built in one
        pass is a model nobody sees until it is finished, and this board is how
        the work gets looked at: the user reads the television, not the code.
        So get the rough shape on the screen early — the silhouette and the
        named parts — and refine it against what the TV actually shows, because
        how a model reads at six by six from a sofa is settled up there rather
        than in a viewport. Each pass is the file, then `reload_mesh`: the
        widget re-reads it in place and keeps its id, its place, its size, its
        description and its colours. Removing and re-adding it to see a change
        costs all of those, every pass.

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
        said = ", ".join(f"{name}={value:g}" for name, value in given.items())
        return await _write(item, model.model_copy(update=given), said)

    @server.tool()
    async def reload_mesh(target: str) -> str:
        """Re-read a model's file, keeping everything else about the widget.

        For the loop `add_mesh` describes: block a model out, put it on the
        board, look at the television, refine the file, say this. The widget
        reads its geometry once when it appears and never again, so a better
        version written over the same path is invisible until something asks —
        and nothing on screen says the model up there is not the model on disk.

        This is the something. The widget keeps its id, its place, its size, its
        description and any colours `color_mesh` gave it; only the geometry is
        read again. Removing and adding the widget also works and costs all of
        those on every pass, which is what this exists to stop.

        Nothing is cached on this side — the wireframe is rebuilt from the file
        for whoever asks — so this is a nudge to the browsers looking, not an
        invalidation. A board nobody has open does its re-reading when somebody
        opens it.
        """
        found = _mesh(target)
        if found is None:
            return f"No mesh widget {target!r}. Call list_items to see what is there."
        item, model = found
        # Not an item update: nothing about the widget changed. Sending one
        # would rewrite the board file and make every *other* client redraw a
        # widget whose payload is identical — see `item.waking` for the same
        # shape, a signal that is not board state.
        await hub.broadcast("mesh.reloaded", {"id": item.id})
        return f"Told {item.id} to read {model.path} again"

    @server.tool()
    async def color_mesh(
        target: str,
        colors: dict | None = None,
        wave: str | None = None,
        wave_colors: list[str] | None = None,
        wave_seconds: float | None = None,
        wave_spread: float | None = None,
    ) -> str:
        """Colour a model's parts, and set a colour running through it.

        A wireframe is lines, so colour is most of what it has to say with. Two
        ways to use it, and they compose.

        `colors` paints named parts and keeps them that way. The keys are the
        part names inside the file — list_items does not show them, but the
        names come from whatever wrote the model, and a generated one names its
        parts after what they are. A key may be a glob:

            colors={"encoder_*": "chart-2", "refine_block": "accent"}

        Longest matching pattern wins, so a name always beats a wildcard. It is
        written whole, like a chart: pass the full set each time, and pass an
        empty one to go back to the widget's own colour.

        `wave` sets a colour travelling through the model, over and over, which
        is the thing that makes the widget read as switched on rather than
        printed. "stack" runs it bottom to top — on a model built as a pipeline
        that is the data going through it. "loop" runs it around the upright
        axis instead, lighting parts in the order they sit around the circle
        and leaving anything standing on the axis at the widget's own colour.
        "off" removes it.

        `wave_colors` is the ramp, in order, and it wraps — the last leads back
        to the first. `wave_seconds` is how long one pass takes; slow is right,
        for the same reason the spin is slow. `wave_spread` is how much of the
        ramp the model holds at once: at 1 the two ends of the object are a
        full cycle apart, and above 1 the ramp repeats so the wave has more than
        one crest.

        A part named in `colors` keeps its colour and does not take the wave.
        That is how to pin the parts that mean something and let the rest
        breathe.
        """
        found = _mesh(target)
        if found is None:
            return f"No mesh widget {target!r}. Call list_items to see what is there."
        item, model = found
        update: dict[str, object] = {}
        said = []

        if colors is not None:
            update["colors"] = colors or None
            said.append(f"{len(colors)} part colours" if colors else "no part colours")

        if wave == "off":
            update["wave"] = None
            said.append("wave off")
        elif wave is not None or wave_colors or wave_seconds or wave_spread:
            # Built on whatever is already there, so turning the speed up does
            # not also silently discard the ramp somebody chose.
            base = model.wave.model_dump() if model.wave else {"colors": list(DEFAULT_RAMP)}
            asked = {
                "mode": wave,
                "colors": wave_colors,
                "seconds": wave_seconds,
                "spread": wave_spread,
            }
            base.update({k: v for k, v in asked.items() if v is not None})
            try:
                update["wave"] = MeshWave.model_validate(base)
            except ValueError as exc:
                return f"Not set: {exc}"
            said.append(f"{base['mode']} wave" if wave else "wave adjusted")

        if not update:
            return "Nothing to set: pass colors, or one of wave / wave_colors / wave_seconds"
        return await _write(item, model.model_copy(update=update), ", ".join(said))
