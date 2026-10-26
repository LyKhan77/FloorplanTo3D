import pytest
from pygltflib import GLTF2

from core.build_prep.mesh import prism
from tests.builder.helpers import build, doc, mesh, rect, skip_without_blender

pytestmark = [pytest.mark.blender, skip_without_blender]


def test_world_mesh_exports_one_to_one_with_axes(tmp_path):
    d = doc([mesh("wall_W1", "Walls", prism(rect(0, 0, 1000, 2000), 0, 3000), props={"spec_id": "W1"})])
    r = build(tmp_path, d)
    assert r.returncode == 0, r.stderr[-2000:]
    g = GLTF2().load(str(tmp_path / "out" / "shell.glb"))
    node = next(n for n in g.nodes if n.name == "wall_W1")
    acc = g.accessors[g.meshes[node.mesh].primitives[0].attributes.POSITION]
    # spec x 0..1 m -> glTF x; spec z 0..3 m -> glTF y (up); spec y 0..2 m (north) -> glTF z = -y
    assert acc.min == pytest.approx([0, 0, -2], abs=1e-6) and acc.max == pytest.approx([1, 3, 0], abs=1e-6)


def test_missing_input_fails_nonzero(tmp_path):
    import subprocess

    from tests.builder.helpers import BLENDER
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "-P", "builder/build.py", "--",
                        str(tmp_path / "nope.json"), str(tmp_path / "out")], capture_output=True, text=True,
                       timeout=300, check=False)
    assert r.returncode != 0
