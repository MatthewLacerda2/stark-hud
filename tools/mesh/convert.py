#!/usr/bin/env python3
"""Turn any 3D file this machine can read into the OBJ the board draws.

    python tools/mesh/convert.py ~/Downloads/helmet.fbx
    python tools/mesh/convert.py scene.blend -o ~/models/scene.obj
    python tools/mesh/convert.py big.glb --max-edges 8000

FBX, glTF, GLB, OBJ, STL, PLY, USD and .blend all go in; one OBJ comes out,
holding the mesh and nothing else. It is written beside the input unless ``-o``
says otherwise, and the path it wrote is the last thing printed, so it can be
passed straight to ``add_mesh``.

This file runs in two places and knows which one it is in. Started from a shell
it finds Blender and re-runs itself inside it; started by Blender — which is how
``bpy`` comes to be importable — it does the work. One file rather than a
driver and a worker, because the export settings below are the whole of "only
the mesh matters" and they should exist exactly once.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import bpy
except ImportError:  # Outside Blender, which is the normal way to start this.
    bpy = None  # type: ignore[assignment]

# How the board reads a model. Kept in step with ``MAX_EDGES`` in
# ``backend/services/mesh.py`` — that one refuses, this one avoids the refusal —
# and deliberately under it, because an export lands a little either side of
# whatever ratio the decimator was given.
DEFAULT_MAX_EDGES = 32_000

# Which importer reads what. `.blend` is not in here because a Blender file is
# not imported at all: it is opened, which replaces the whole scene.
#
# FBX is read by `wm.fbx_import`, Blender's built-in one, and not by the older
# `import_scene.fbx` that ships beside it. The Python importer in 5.2 raises on
# any file containing a light — it sets `cast_shadow` on a Cycles light, which
# no longer exists — and a downloaded FBX nearly always has lights in it. The
# built-in one reads the same files and does not care.
IMPORTERS = {
    ".obj": "wm.obj_import",
    ".fbx": "wm.fbx_import",
    ".gltf": "import_scene.gltf",
    ".glb": "import_scene.gltf",
    ".stl": "wm.stl_import",
    ".ply": "wm.ply_import",
    ".usd": "wm.usd_import",
    ".usdc": "wm.usd_import",
    ".usda": "wm.usd_import",
    ".usdz": "wm.usd_import",
}

READABLE = [*sorted(IMPORTERS), ".blend"]


# --------------------------------------------------------------- inside Blender
def export_obj(path: Path) -> None:
    """Write every object in the scene as one OBJ: mesh, and nothing else.

    Materials, normals, UVs and vertex colours are all off, and this is the one
    place that decision is written down. The board draws edges in a single
    colour, so every one of those flags left on writes data whose only
    destination is a parser that skips it — and a normal per corner is bigger
    than the geometry it describes.

    Nothing is triangulated on the way out. A quad is two triangles, and the
    diagonal through every one of them is a line on the television that the
    object itself does not have.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.obj_export(
        filepath=str(path),
        export_selected_objects=False,
        export_materials=False,
        export_normals=False,
        export_uv=False,
        export_colors=False,
        export_triangulated_mesh=False,
        apply_modifiers=True,
    )


def _meshes() -> list["bpy.types.Object"]:
    """Every mesh in the scene."""
    return [one for one in bpy.context.scene.objects if one.type == "MESH"]


def _load(source: Path) -> None:
    """Open or import the file, leaving the scene holding only its meshes.

    Cameras, lights, armatures, empties and curves are all deleted rather than
    ignored. An exported camera would arrive as an ``o`` line with a handful of
    vertices, and the widget would draw it — a small wire pyramid floating
    beside the model, which is a puzzle rather than a fault.
    """
    if source.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source))
    else:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()
        group, _, operator = IMPORTERS[source.suffix.lower()].partition(".")
        getattr(getattr(bpy.ops, group), operator)(filepath=str(source))

    bpy.ops.object.select_all(action="DESELECT")
    for one in list(bpy.context.scene.objects):
        if one.type != "MESH":
            one.select_set(True)
    bpy.ops.object.delete()


def _edges() -> int:
    """How many lines the board would be asked to draw for this scene."""
    return sum(len(one.data.edges) for one in _meshes())


def _dissolve() -> None:
    """Merge faces that are already flat, so the wireframe shows the object.

    This is the single biggest thing between a downloaded model and one that is
    readable from a sofa. Almost everything on the internet arrives
    triangulated, and a wireframe draws every edge it is given — so the flat
    side of a box comes through as a field of diagonals that belong to the file
    format rather than to the object. Dissolving the edges between coplanar
    faces puts that side back to the four lines it actually has.

    It is done before any decimation, not after, because it is also free
    reduction: on a triangulated model it often takes the edge count under the
    budget on its own, and edges removed this way cost nothing in shape, while
    every edge the decimator removes costs a little.
    """
    for one in _meshes():
        bpy.context.view_layer.objects.active = one
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_limited(angle_limit=0.0174533)
        bpy.ops.object.mode_set(mode="OBJECT")


def _decimate(ratio: float) -> None:
    """Throw away faces until the model fits, keeping its shape as far as it can.

    Collapse rather than any of the other modes, because it is the one that
    works on an arbitrary mesh. It triangulates what it touches, which is a real
    loss — see ``_dissolve`` for why triangles read badly — but a model that has
    to be decimated is one that arrived triangulated anyway.
    """
    for one in _meshes():
        modifier = one.modifiers.new(name="board-fit", type="DECIMATE")
        modifier.ratio = ratio


def _inside_blender(source: Path, target: Path, max_edges: int) -> None:
    """Do the conversion. Everything this touches is Blender's own state."""
    _load(source)
    if not _meshes():
        print(f"Nothing to draw: no mesh in {source}", file=sys.stderr)
        raise SystemExit(1)

    before = _edges()
    _dissolve()
    flattened = _edges()
    if flattened > max_edges:
        _decimate(max_edges / flattened)
    export_obj(target)
    print(
        f"{source.name}: {before:,} edges -> {flattened:,} flattened"
        + (f" -> about {max_edges:,} decimated" if flattened > max_edges else "")
    )
    print(target)


# ------------------------------------------------------------------ on the host
def _blender() -> str:
    """Where Blender is, or a sentence saying it is the one thing missing."""
    found = shutil.which("blender")
    if found is None:
        print(
            "Blender is not on PATH, and it is what reads these formats. "
            "Install it (`pacman -S blender`) and run this again.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return found


def stamp(target: Path) -> float:
    """When the target was last written, or 0 when it is not there yet."""
    return target.stat().st_mtime if target.exists() else 0.0


def _drive(source: Path, target: Path, max_edges: int) -> int:
    """Run Blender on this file and pass its output through, or say why not.

    ``--factory-startup`` so that whatever add-ons and preferences happen to be
    on this machine cannot change what comes out; a conversion that depends on
    somebody's viewport settings is not a conversion.
    """
    before = stamp(target)

    def written(path: Path) -> bool:
        """Whether this run produced the file, rather than a previous one."""
        return stamp(path) > before

    done = subprocess.run(
        [
            _blender(),
            "--background",
            "--factory-startup",
            "--python",
            str(Path(__file__).resolve()),
            "--",
            str(source),
            str(target),
            str(max_edges),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # Blender writes a banner, add-on chatter and timings to stdout whatever it
    # is asked to do, so only the lines this script printed are passed on. The
    # last of them is the path, which is what a caller wants to read.
    for line in done.stdout.splitlines():
        if line.startswith(source.name) or line == str(target):
            print(line)

    # Whether the file appeared, not what Blender's exit code says. An importer
    # that raises inside Blender is caught by Blender, reported as an `Error:`
    # on its own output, and then exits 0 — so trusting the status code meant a
    # conversion that wrote nothing at all finished without a word, which is the
    # worst way for this to fail. What was asked for was a file; the file being
    # there is the only thing worth checking.
    if written(target):
        return 0
    print(f"Blender wrote no OBJ for {source.name}. What it said:", file=sys.stderr)
    print(_why(done.stderr, done.stdout), file=sys.stderr)
    return done.returncode or 1


def _why(*output: str) -> str:
    """The line that says what went wrong, out of everything Blender printed.

    Blender reports a failed operator as a line beginning ``Error:``, which is
    the one line worth reading, and this machine's Blender also prints an
    unrelated traceback at every startup — its extensions add-on wants a module
    that is not installed. Leading with that buries the real reason under six
    frames about something nobody asked for, so the recognisable lines are
    preferred and everything is shown only when none of them is there.
    """
    lines = [line for text in output for line in text.splitlines()]
    named = [line for line in lines if line.startswith(("Error:", "Nothing to draw"))]
    return "\n".join(named or lines).strip()


def main() -> int:
    """Parse arguments on the host, or read the three Blender was handed."""
    if bpy is not None:
        source, target, budget = sys.argv[sys.argv.index("--") + 1 :][:3]
        _inside_blender(Path(source), Path(target), int(budget))
        return 0

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help=f"a file ending {', '.join(READABLE)}")
    parser.add_argument("-o", "--out", type=Path, help="where to write the OBJ")
    parser.add_argument(
        "--max-edges",
        type=int,
        default=DEFAULT_MAX_EDGES,
        help=f"the board's budget, default {DEFAULT_MAX_EDGES:,}",
    )
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    if not source.is_file():
        print(f"No file at {source}", file=sys.stderr)
        return 1
    if source.suffix.lower() not in READABLE:
        print(f"Cannot read {source.suffix}: try one of {', '.join(READABLE)}", file=sys.stderr)
        return 1

    target = (args.out or source.with_suffix(".obj")).expanduser().resolve()
    if target == source:
        target = source.with_name(f"{source.stem}-board.obj")
    return _drive(source, target, args.max_edges)


if __name__ == "__main__":
    raise SystemExit(main())
