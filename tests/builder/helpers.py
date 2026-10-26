"""Shared helpers for tests that run the Blender builder."""

import json
import os
import subprocess
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from core.build_prep.mesh import box, prism
from core.build_prep.schema import BUILD_INPUT_VERSION, MATERIALS
from core.config import load_settings

BLENDER = load_settings().blender_bin
skip_without_blender = pytest.mark.skipif(not os.access(BLENDER, os.X_OK), reason="Blender not found")
DEFAULT_EXPORTS = [
    {"file": "shell.glb", "collections": ["Shell"]},
    {"file": "layout_full.glb", "collections": ["Shell", "Objects"]},
    {"file": "layout.blend", "collections": []},
    {"file": "layout.fbx", "collections": ["Shell", "Objects"]},
    {"file": "layout.obj", "collections": ["Shell", "Objects"]},
]


def build(tmp_path: Path, doc: dict) -> subprocess.CompletedProcess:
    inp = tmp_path / "build_input.json"
    inp.write_text(json.dumps(doc))
    return subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "-P", "builder/build.py",
                           "--", str(inp), str(tmp_path / "out")], capture_output=True, text=True, timeout=300,
                          check=False)


def mesh(name, collection, m, material="wall_ext", props=None, parent=None, location=(0, 0, 0)):
    return {"name": name, "collection": collection, "verts": m["verts"], "faces": m["faces"], "material": material,
            "props": props or {}, "parent": parent, "location": list(location), "rot_z": 0.0}


def doc(meshes, empties=(), cutters=(), labels=(), exports=None):
    return {"version": BUILD_INPUT_VERSION, "spec_version": 1, "materials": MATERIALS, "meshes": list(meshes),
            "empties": list(empties), "cutters": list(cutters), "instances": [], "labels": list(labels),
            "grid_lines": [], "cameras": [], "render": {"engine": "BLENDER_WORKBENCH"},
            "exports": exports or DEFAULT_EXPORTS}


def rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def minimal_doc():
    wall = mesh("wall_W1", "Walls", prism(rect(0, -100, 1000, 100), 0, 3000),
                props={"spec_id": "W1", "spec_type": "wall", "spec_version": 1, "height_mm": 3000})
    door = {"name": "door_D1", "collection": "Doors", "location": [2000, 0, 0], "rot_z": 0.0,
            "props": {"spec_id": "D1", "spec_type": "door"}, "parent": None}
    leaf = mesh("leaf_D1_a", "Doors", box(450, 0, 1045, 900, 40, 2090), "door_leaf",
                {"spec_id": "D1", "spec_type": "door"}, parent="door_D1")
    return doc([wall, leaf], empties=[door])


def two_walls_corner_with_cutter_doc():
    w1 = mesh("wall_W1", "Walls", prism(rect(0, -100, 1000, 100), 0, 3000), props={"spec_id": "W1"})
    w2 = mesh("wall_W2", "Walls", prism(rect(1000, -100, 1200, 1000), 0, 3000), props={"spec_id": "W2"})
    cut = box(900, 0, 1050, 400, 220, 2100)  # x 700..1100: crosses into W2's footprint
    return doc([w1, w2], cutters=[{"target": "wall_W1", "verts": cut["verts"], "faces": cut["faces"]}])


def tri_count(g, name: str) -> int:
    node = next(n for n in g.nodes if n.name == name)
    return sum(g.accessors[p.indices].count // 3 for p in g.meshes[node.mesh].primitives)
