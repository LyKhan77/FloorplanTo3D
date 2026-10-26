import pytest
from pygltflib import GLTF2

from tests.builder.helpers import (
    build,
    minimal_doc,
    skip_without_blender,
    tri_count,
    two_walls_corner_with_cutter_doc,
)

pytestmark = [pytest.mark.blender, skip_without_blender]


def test_meshes_props_and_hierarchy_in_glb(tmp_path):
    r = build(tmp_path, minimal_doc())
    assert r.returncode == 0, r.stderr[-2000:]
    assert "@@PROGRESS 100" in r.stdout
    g = GLTF2().load(str(tmp_path / "out" / "shell.glb"))
    assert {"wall_W1", "door_D1", "leaf_D1_a"} <= {n.name for n in g.nodes}
    w = next(n for n in g.nodes if n.name == "wall_W1")
    assert w.extras == {"spec_id": "W1", "spec_type": "wall", "spec_version": 1, "height_mm": 3000}
    door = next(n for n in g.nodes if n.name == "door_D1")
    leaf_idx = next(i for i, n in enumerate(g.nodes) if n.name == "leaf_D1_a")
    assert leaf_idx in door.children


def test_cutter_only_cuts_its_wall(tmp_path):
    r = build(tmp_path, two_walls_corner_with_cutter_doc())
    assert r.returncode == 0, r.stderr[-2000:]
    g = GLTF2().load(str(tmp_path / "out" / "shell.glb"))
    assert tri_count(g, "wall_W1") > 12 and tri_count(g, "wall_W2") == 12


def test_all_export_files_exist(tmp_path):
    assert build(tmp_path, minimal_doc()).returncode == 0
    for f in ("shell.glb", "layout_full.glb", "layout.blend", "layout.fbx", "layout.obj", "layout.mtl"):
        assert (tmp_path / "out" / f).stat().st_size > 0


def test_annotations_not_exported(tmp_path):
    d = minimal_doc()
    d["labels"] = [{"text": "R1", "location": [500, 500], "size": 300}]
    assert build(tmp_path, d).returncode == 0
    g = GLTF2().load(str(tmp_path / "out" / "shell.glb"))
    assert not any((n.name or "").startswith("label_") for n in g.nodes)
