"""The objects the mesh widget was written against, built from scratch in Blender.

Run inside Blender, never on its own — ``bpy`` only exists in there:

    blender --background --factory-startup --python tools/mesh/samples.py -- state/models

Two objects, and each is here for a reason. ``cube.obj`` is the smoke test: eight
vertices and twelve edges, so whether the spin is right is something you can
settle by eye rather than by argument. ``reactor.obj`` is the real one, in four
separate parts, which is what makes the exploded view worth looking at.

Modelled from primitives with no booleans and no modifiers. A wireframe draws
every edge of what it is given, so a mesh that was cut out of another mesh
arrives as a thicket of little triangles around the cut — which reads as noise
from a sofa. Cylinders and a torus at low segment counts read as a machine.

Nothing is triangulated on the way out for the same reason: a quad is two
triangles, and the diagonal through every one of them is a line on the screen
that nothing in the object actually has.
"""

import math
import sys
from pathlib import Path

import bpy
import mathutils

# Blender does not put the running script's directory on the path, so a script
# it is given cannot import the module next to it without being told where that
# is. Worth the two lines: `export_obj` is where "only the mesh matters" is
# written down, and a second copy of it here is a second copy that can drift.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from convert import export_obj

# How round a round thing looks. Low on purpose: this is drawn as lines on a
# television, and past about two dozen segments the extra edges stop reading as
# curvature and start filling the shape in.
SEGMENTS = 24
COIL_SEGMENTS = 8
COIL_COUNT = 8


def _clear() -> None:
    """Empty the scene, including the cube Blender starts every file with."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _named(name: str) -> "bpy.types.Object":
    """Name whatever was just added, and hand it back.

    The name matters more here than it looks: the OBJ exporter writes it as an
    ``o`` line, that is what the parser turns into a part, and a part is what the
    exploded view moves. An object called ``Cylinder.003`` explodes just as well
    and tells nobody anything.
    """
    made = bpy.context.active_object
    made.name = name
    made.data.name = name
    return made


def _ring(name: str, radius: float, thickness: float, z: float) -> "bpy.types.Object":
    """A torus lying flat, at a height."""
    bpy.ops.mesh.primitive_torus_add(
        major_radius=radius,
        minor_radius=thickness,
        major_segments=SEGMENTS,
        minor_segments=6,
        location=(0.0, 0.0, z),
    )
    return _named(name)


def _disc(
    name: str, radius: float, depth: float, z: float, segments: int = SEGMENTS
) -> "bpy.types.Object":
    """A cylinder standing on the Z axis, centred at a height."""
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=depth, vertices=segments, location=(0.0, 0.0, z)
    )
    return _named(name)


def _coils() -> "bpy.types.Object":
    """The ring of little cylinders, as one object rather than eight.

    Joined because a part is a thing that moves as a unit in the exploded view,
    and eight coils flying apart from each other is not what an exploded diagram
    of a reactor shows — the coil assembly comes away from the housing whole.
    """
    made = []
    for i in range(COIL_COUNT):
        angle = 2 * math.pi * i / COIL_COUNT
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.09,
            depth=0.24,
            vertices=COIL_SEGMENTS,
            location=(0.55 * math.cos(angle), 0.55 * math.sin(angle), 0.04),
        )
        made.append(bpy.context.active_object)
    bpy.ops.object.select_all(action="DESELECT")
    for one in made:
        one.select_set(True)
    bpy.context.view_layer.objects.active = made[0]
    bpy.ops.object.join()
    return _named("coils")


def _face_the_viewer() -> None:
    """Stand the whole assembly up so it faces front rather than lying on its back.

    Everything above is modelled the way one models a disc: flat on the ground,
    thickness up the Z axis. The exporter then turns Blender's Z-up into the Y-up
    that OBJ and every browser use — Blender +Z becomes OBJ +Y — which leaves a
    reactor pointing at the ceiling. Turning it a quarter turn about X first
    makes the two conversions cancel, and the vertices come out exactly as they
    were modelled.

    The matrix is applied by hand rather than through ``transform.rotate``, which
    turns things about the median of what is selected. With four parts stacked
    along the axis, that median is not the origin, so the operator quietly moved
    the whole assembly sideways as well as turning it — an offset of about a
    tenth of a unit that is invisible in a viewport and obvious on a television.
    """
    turn = mathutils.Matrix.Rotation(math.radians(90), 4, "X")
    for one in bpy.context.scene.objects:
        one.matrix_world = turn @ one.matrix_world
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=False)


def build_cube(into: Path) -> None:
    """Twelve edges, so a wrong rotation has nowhere to hide."""
    _clear()
    bpy.ops.mesh.primitive_cube_add(size=1.4)
    _named("cube")
    export_obj(into / "cube.obj")


def build_reactor(into: Path) -> None:
    """Four parts, stacked along the axis they come apart on.

    Depths are what put the exploded view in order: the housing sits at the back,
    the coils and their ring in the middle, the core proud at the front. Explode
    pushes each part out along the line from the middle of the object to the
    middle of that part, so parts that are already stacked come apart in the
    order they were assembled.

    That rule is also why the coils sit a little behind the ring rather than
    level with it. Both are rings around the same axis, so both have a centroid
    on that axis, and level with each other they had the *same* centroid — which
    exploded means travelling together and never coming apart. Depth is the only
    thing separating two concentric parts, so they are given different depths.
    """
    _clear()
    _disc("housing", radius=1.0, depth=0.16, z=-0.05)
    _ring("outer_ring", radius=0.82, thickness=0.07, z=0.10)
    _coils()
    _disc("core", radius=0.26, depth=0.34, z=0.26, segments=16)
    _face_the_viewer()
    export_obj(into / "reactor.obj")


def main() -> None:
    """Write both samples into the directory named after ``--``, or ``state/models``."""
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    into = Path(argv[0]).expanduser().resolve() if argv else Path.cwd() / "state" / "models"
    build_cube(into)
    build_reactor(into)
    print(f"wrote cube.obj and reactor.obj into {into}")


if __name__ == "__main__":
    main()
