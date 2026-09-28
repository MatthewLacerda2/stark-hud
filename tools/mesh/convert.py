#!/usr/bin/env python3
"""Turn anything Blender can open into the .glb the board shows.

    python tools/mesh/convert.py ~/Downloads/helmet.blend
    python tools/mesh/convert.py scene.fbx -o ~/models/scene.glb

.blend, FBX, glTF, OBJ, STL, PLY and USD all go in; one .glb comes out, holding
the objects, their names, their pivots and their animation. It is written
beside the input unless ``-o`` says otherwise, and the path it wrote is the last
thing printed, so it can be passed straight to ``add_mesh``.

The board opens .glb, .gltf, .fbx and .obj itself, so this is for the rest —
above all a .blend, which only Blender reads and which is the thing someone
hands over. Nothing is simplified on the way through: the widget draws the edges
it finds sharp and lets the rest go, so a triangulated model reads as well as a
tidy one.

This file runs in two places and knows which one it is in. Started from a shell
it finds Blender and re-runs itself inside it; started by Blender — which is how
``bpy`` comes to be importable — it does the work. One file rather than a
driver and a worker, because the export settings below should exist exactly
once.
"""

# The one file here that runs under an interpreter this project does not pick:
# Blender's own. Annotations below name `bpy.types`, and outside Blender `bpy`
# is None — which is fine on 3.14, where an annotation is never evaluated, and
# an AttributeError at import on anything older. This line makes it fine on
# both.
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import bpy
except ImportError:  # Outside Blender, which is the normal way to start this.
    bpy = None  # type: ignore[assignment]

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
def export_glb(path: Path) -> None:
    """Write the scene as one .glb: objects, pivots, loose lines and animation.

    Cameras and lights are left out — the board brings its own camera, and its
    own light, which is no light at all. Materials go too: the look is the
    board's, and a material nothing reads is bytes for nobody. Loose edges are
    kept (``use_mesh_edges``), because a model built partly of lines — a cable,
    a path, a point cloud drawn as crosses — is lines on purpose.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        export_cameras=False,
        export_lights=False,
        export_materials="NONE",
        export_animations=True,
        export_apply=True,
        use_mesh_edges=True,
    )


def _meshes() -> list[bpy.types.Object]:
    """Every mesh in the scene."""
    return [one for one in bpy.context.scene.objects if one.type == "MESH"]


def _load(source: Path) -> None:
    """Open or import the file into an empty scene.

    Nothing is deleted after. Empties and armatures are how a file says where a
    part turns about and what moves it, and throwing them away — which the OBJ
    route had to — is throwing away the fan's axle. Cameras and lights are left
    for the exporter to skip.
    """
    if source.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source))
        return
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    group, _, operator = IMPORTERS[source.suffix.lower()].partition(".")
    getattr(getattr(bpy.ops, group), operator)(filepath=str(source))


def _inside_blender(source: Path, target: Path) -> None:
    """Do the conversion. Everything this touches is Blender's own state."""
    _load(source)
    if not _meshes():
        print(f"Nothing to draw: no mesh in {source}", file=sys.stderr)
        raise SystemExit(1)
    export_glb(target)
    print(f"{source.name}: {len(_meshes())} objects")
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


def _drive(source: Path, target: Path) -> int:
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
    print(f"Blender wrote no .glb for {source.name}. What it said:", file=sys.stderr)
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
        source, target = sys.argv[sys.argv.index("--") + 1 :][:2]
        _inside_blender(Path(source), Path(target))
        return 0

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help=f"a file ending {', '.join(READABLE)}")
    parser.add_argument("-o", "--out", type=Path, help="where to write the .glb")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    if not source.is_file():
        print(f"No file at {source}", file=sys.stderr)
        return 1
    if source.suffix.lower() not in READABLE:
        print(f"Cannot read {source.suffix}: try one of {', '.join(READABLE)}", file=sys.stderr)
        return 1

    target = (args.out or source.with_suffix(".glb")).expanduser().resolve()
    if target == source:
        target = source.with_name(f"{source.stem}-board.glb")
    return _drive(source, target)


if __name__ == "__main__":
    raise SystemExit(main())
