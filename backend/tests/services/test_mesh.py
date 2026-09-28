"""Finding a model's file, and saying what kind it is."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas.mesh import MeshPayload
from services import mesh


@pytest.mark.parametrize("name", ["pc.glb", "scene.gltf", "rig.FBX", "cloud.obj"])
def test_what_a_browser_can_open_is_taken(name: str) -> None:
    assert MeshPayload(path=f"/models/{name}").path == f"/models/{name}"


def test_a_blend_is_sent_to_the_converter() -> None:
    """Only Blender reads a .blend, and Blender is not in the container."""
    with pytest.raises(ValidationError) as raised:
        MeshPayload(path="/models/pc.blend")
    assert "tools/mesh/convert.py /models/pc.blend" in str(raised.value)


def test_a_file_is_named_for_what_it_is(tmp_path: Path) -> None:
    """A glb goes as a glb, so the browser is never left to sniff it."""
    model = tmp_path / "pc.glb"
    model.write_bytes(b"glTF")
    assert mesh.file_of(str(model)) == (model, "model/gltf-binary")


def test_a_missing_file_is_not_an_error(tmp_path: Path) -> None:
    """It is the thing the caller is watching for, not a failure."""
    assert mesh.file_of(str(tmp_path / "gone.glb")) is None
