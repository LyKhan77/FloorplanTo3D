import json
import os
import subprocess
from pathlib import Path

import pytest
from pygltflib import GLTF2

from core.config import load_settings

BLENDER = load_settings().blender_bin
pytestmark = [
    pytest.mark.blender,
    pytest.mark.skipif(not os.access(BLENDER, os.X_OK), reason="Blender not found"),
]


def run_build(inp: Path, out: Path):
    return subprocess.run(
        [BLENDER, "-b", "--factory-startup", "--python-exit-code", "1",
         "-P", "builder/build.py", "--", str(inp), str(out)],
        capture_output=True, text=True, timeout=300, check=False,
    )


def test_box_exports_with_extras_and_axes(tmp_path):
    inp = tmp_path / "build_input.json"
    inp.write_text(json.dumps({"version": 0, "boxes": [{
        "name": "wall_W1", "min_mm": [0, 0, 0], "size_mm": [1000, 2000, 3000],
        "props": {"spec_id": "W1", "spec_type": "wall"}}]}))
    r = run_build(inp, tmp_path / "out")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "@@PROGRESS 100" in r.stdout
    g = GLTF2().load(str(tmp_path / "out" / "shell.glb"))
    node = next(n for n in g.nodes if n.name == "wall_W1")
    assert node.extras["spec_id"] == "W1" and node.extras["spec_type"] == "wall"
    # center spec (0.5, 1.0, 1.5) m -> glTF Y-up (x, z, -y)
    assert node.translation == pytest.approx([0.5, 1.5, -1.0], abs=1e-6)
    acc = g.accessors[g.meshes[node.mesh].primitives[0].attributes.POSITION]
    ext = [hi - lo for hi, lo in zip(acc.max, acc.min)]
    assert ext == pytest.approx([1.0, 3.0, 2.0], abs=1e-6)  # 1:1 in meters


def test_missing_input_fails_nonzero(tmp_path):
    assert run_build(tmp_path / "nope.json", tmp_path / "out").returncode != 0
