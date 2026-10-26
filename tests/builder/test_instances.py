import pytest
from pygltflib import GLTF2

from core.build_prep.assemble import build_input_for
from core.spec.ops import apply
from tests.builder.helpers import build, skip_without_blender
from tests.spec.fixtures import spec_with_rooms

pytestmark = [pytest.mark.blender, skip_without_blender]


def add_rack(x, y):
    return {"op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.0.0",
            "position": (x, y, 0), "dims": (600, 1200, 2000)}


def test_instances_are_linked_duplicates_and_only_in_full_glb(tmp_path, placeholder_root):
    s = apply(spec_with_rooms(), [add_rack(2000, 2000), add_rack(3000, 2000)], "editor", 2)
    doc, _ = build_input_for(s, placeholder_root, None)
    doc["cameras"] = []
    r = build(tmp_path, doc)
    assert r.returncode == 0, r.stderr[-2000:]
    full = GLTF2().load(str(tmp_path / "out" / "layout_full.glb"))
    shell = GLTF2().load(str(tmp_path / "out" / "shell.glb"))
    assert {"obj_O1", "obj_O2"} <= {n.name for n in full.nodes} and "obj_O1" not in {n.name for n in shell.nodes}
    rack_meshes = {n.mesh for n in full.nodes if n.mesh is not None and (n.name or "").startswith("template_root")}
    assert len(rack_meshes) == 1  # both racks share one mesh (linked duplicates)
