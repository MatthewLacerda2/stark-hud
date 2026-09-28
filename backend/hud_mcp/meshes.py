"""The MCP tools for the mesh widget: put a model on the board, and turn it.

Two tools, split the way the media widget's are. ``add_mesh`` says which model,
and after that the file never changes; ``set_mesh`` is how the thing is looked
at — turned, tilted, framed, pulled apart — because a model on the board is
watched and adjusted rather than rewritten.

The browser reads .glb, .gltf, .fbx and .obj itself. A .blend, or anything else
Blender opens, goes through ``tools/mesh/convert.py`` first, which drives
Blender on the host and writes a .glb beside whatever it was given.
"""

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import ON_HOST, add, typed
from schemas.board import ItemRead, ItemUpdate, MeshPayload, MeshWave
from services import board as service
from services import events
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
        return typed(target, MeshPayload)

    async def _write(item: ItemRead, payload: MeshPayload, said: str) -> str:
        """Validate the new payload and store it. The service tells every board."""
        try:
            # Validated rather than trusted: model_copy does not run the field
            # bounds, so a spin of 400 would sit in the payload and reach the
            # browser as a model turning too fast to be a model.
            checked = MeshPayload.model_validate(payload.model_dump())
            await service.update(item, ItemUpdate(payload=checked))
        except ValueError as exc:
            return f"Not set: {exc}"
        except SlotTakenError as exc:
            return f"Not set: {exc}"
        return f"Set {said} on {item.id}"

    @server.tool(annotations=ON_HOST)
    async def add_mesh(
        path: str,
        spin: float = 0.0,
        heading: float = 0.0,
        tilt: float = 16.0,
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
        parent_id: str | None = None,
        description: str | None = None,
    ) -> str:
        """Show a 3D model — something made in Blender — as a hologram.

        `path` is a model file on the machine running the board: .glb, .gltf
        (self-contained), .fbx or .obj. A .blend, or anything else Blender
        opens, is converted first:

            python tools/mesh/convert.py ~/Downloads/helmet.blend

        which writes `helmet.glb` beside it and prints the path to pass here.

        What is drawn is the file's parts as they were built — their names,
        their pivots, and any animation saved in the file, which plays on a
        loop — in the board's own look: translucent light, brighter toward the
        outline, with glowing edges. Materials, textures and cameras in the file
        are ignored. The model is framed to fit the widget whatever units it was
        saved in, so it never needs a scale.

        The board is a flat sheet, and the model is drawn flat onto it: nothing
        fakes depth. It holds still by default at `heading` degrees (turned
        counter-clockwise, seen from above) and `tilt` degrees of looking down.
        `spin` turns it on a turntable instead, in turns per second — slowly,
        if at all. Everything else about the view is `set_mesh`.

        A node can carry words: give it a `label` in its glTF extras (in
        Blender, a custom property named `label` on the object). The label is
        written beside the node's own origin, in the board's type, and follows
        it as the model turns, animates or explodes. When labels crowd, the one
        earlier in the file is drawn and the later one waits — so put first
        what matters most (Blender writes objects in name order). Labels keep
        the widget's ink; `colors` does not reach them.

        Give it room: a model is a shape to recognise, and below about 4 by 4
        the lines converge.

        Build it, put it up, then make it good: each pass is the file, then
        `reload_mesh` — the widget re-reads it in place and keeps its id, its
        place, its size, its description and its colours.

        This is the one widget that removes itself when its file goes missing,
        rather than showing a placeholder. If the model is on a drive that is not
        always mounted, expect the widget to be gone after a reboot — a line in
        the inbox says which file it was.
        """
        try:
            payload = MeshPayload(path=path, spin=spin, heading=heading, tilt=tilt)
        except ValueError as exc:
            return f"Not added: {exc}"
        return await add(payload, x, y, w, h, parent_id, description=description)

    @server.tool()
    async def set_mesh(
        target: str,
        spin: float | None = None,
        sweep: float | None = None,
        heading: float | None = None,
        tilt: float | None = None,
        fov: float | None = None,
        zoom: float | None = None,
        pan_x: float | None = None,
        pan_y: float | None = None,
        explode: float | None = None,
    ) -> str:
        """Change how a model is looked at: turned, framed, or pulled apart.

        `heading` is where it stands, in degrees counter-clockwise seen from
        above; 0 is the model's front toward the viewer. `tilt` is how far above
        it the camera sits. `spin` turns it on a turntable, turns per second, 0
        holds it still; `sweep` swings it that many degrees each way instead of
        going round, at `spin`'s pace.

        `fov` is the camera's field of view in degrees (narrow flattens, wide
        exaggerates); the model is re-framed to fit either way. `zoom` scales it
        against that fit — above 1 crops in. `pan_x` / `pan_y` slide it across
        the widget, as a fraction of the widget's width and height.

        `explode` pulls the parts apart along the line from the middle, 0 to 1 —
        only as good as the file: one lump has nothing to come apart from.

        Everything is optional and only what you pass moves, the way set_style
        and set_media_mode work. `target` is the widget's id or its key. A mesh
        written by the agent from `state/sources.toml` takes its view from there
        and is set back on the next tick — change the file instead.

        There is no `path` here on purpose: which model a widget shows is what
        the widget *is*, and swapping it would leave the description, the key and
        the size of one model attached to another. Remove it and add the new one.
        """
        found = _mesh(target)
        if found is None:
            return f"No mesh widget {target!r}. Call list_items to see what is there."
        item, model = found
        asked = {
            "spin": spin,
            "sweep": sweep,
            "heading": heading,
            "tilt": tilt,
            "fov": fov,
            "zoom": zoom,
            "pan_x": pan_x,
            "pan_y": pan_y,
            "explode": explode,
        }
        given = {name: value for name, value in asked.items() if value is not None}
        if not given:
            return f"Nothing to set: pass at least one of {', '.join(asked)}"
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
        await events.mesh_reloaded(item.id)
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
