"""Reading an OBJ down to edges: what is kept, what is thrown away, what is refused."""

import pytest

from services import mesh

# A unit cube written the way an exporter writes one: six quads over eight
# shared points. Every interior edge is claimed by two faces, which is what
# makes it the right shape to test deduplication on.
CUBE = """\
o cube
v -1.0 -1.0 -1.0
v -1.0 -1.0 1.0
v -1.0 1.0 -1.0
v -1.0 1.0 1.0
v 1.0 -1.0 -1.0
v 1.0 -1.0 1.0
v 1.0 1.0 -1.0
v 1.0 1.0 1.0
f 1 2 4 3
f 5 7 8 6
f 1 5 6 2
f 3 4 8 7
f 1 3 7 5
f 2 6 8 4
"""


def test_a_cube_is_twelve_lines_not_twenty_four() -> None:
    """Faces share edges, and a shared edge is one stroke on the screen."""
    wire = mesh.parse(CUBE)
    assert len(wire.parts) == 1
    assert len(wire.parts[0].verts) // 3 == 8
    assert len(wire.parts[0].edges) // 2 == 12


def test_everything_that_is_not_geometry_is_dropped() -> None:
    """Normals, texture coordinates and materials change nothing about the result."""
    noisy = CUBE.replace("o cube\n", "o cube\nmtllib thing.mtl\nusemtl Steel\ns 1\n")
    noisy = noisy.replace("f 1 2 4 3", "vn 0.0 0.0 1.0\nvt 0.5 0.5\nf 1/1/1 2/1/1 4/1/1 3/1/1")
    assert mesh.parse(noisy).parts[0].edges == mesh.parse(CUBE).parts[0].edges


def test_a_model_is_centred_and_scaled_to_fit() -> None:
    """Whatever units the file used, the model arrives inside a unit cube."""
    far_away = CUBE.replace("v -1.0", "v 998.0").replace("v 1.0", "v 1000.0")
    wire = mesh.parse(far_away)
    assert max(abs(v) for v in wire.parts[0].verts) == pytest.approx(0.5)
    # The measurement is reported in the units the file used, not the normalised
    # ones, which is the only way to notice a model that arrived in millimetres.
    assert wire.source_size == pytest.approx([2.0, 2.0, 2.0])


def test_named_objects_become_parts() -> None:
    """``o`` is what an exploded view comes apart along."""
    two = CUBE + "o second\nv 5.0 5.0 5.0\nv 6.0 5.0 5.0\nv 6.0 6.0 5.0\nf -3 -2 -1\n"
    assert [part.name for part in mesh.parse(two).parts] == ["cube", "second"]


def test_negative_indices_count_back_from_here() -> None:
    """An OBJ may address the vertex it just wrote as -1, and exporters do."""
    relative = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3 -2 -1\n"
    assert len(mesh.parse(relative).parts[0].edges) // 2 == 3


def test_a_part_only_carries_the_points_it_uses() -> None:
    """OBJ numbers vertices once for the file; a part is remapped to its own."""
    two = CUBE + "o second\nv 5.0 5.0 5.0\nv 6.0 5.0 5.0\nv 6.0 6.0 5.0\nf -3 -2 -1\n"
    second = mesh.parse(two).parts[1]
    assert len(second.verts) // 3 == 3
    assert max(second.edges) == 2


def test_an_empty_object_is_not_a_part() -> None:
    """A file may name an object and give it no faces; nothing is drawn for it."""
    assert [p.name for p in mesh.parse(CUBE + "o empty\n").parts] == ["cube"]


def test_a_file_with_no_faces_is_refused() -> None:
    """Points alone have no edges, and a widget drawing nothing explains nothing."""
    with pytest.raises(mesh.BadMeshError):
        mesh.parse("v 0 0 0\nv 1 1 1\n")


def test_a_face_pointing_past_the_end_is_refused() -> None:
    """Better a sentence naming the index than a widget that silently lost a face."""
    with pytest.raises(mesh.BadMeshError):
        mesh.parse("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 9\n")


def test_too_many_edges_names_the_converter() -> None:
    """The fix is one command, so the refusal says which one."""
    lines = [f"v {i} 0 0" for i in range(mesh.MAX_EDGES + 10)]
    lines += [f"l {i} {i + 1}" for i in range(1, mesh.MAX_EDGES + 5)]
    with pytest.raises(mesh.MeshTooBigError) as raised:
        mesh.parse("\n".join(lines))
    assert "tools/mesh/convert.py" in str(raised.value)


def test_a_missing_file_is_not_an_error() -> None:
    """It is the thing the caller is watching for, so it comes back as None."""
    assert mesh.read("/nowhere/at/all.obj") is None
