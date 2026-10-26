"""Regression tests for the M2 final-review findings."""

import json
import shutil
import subprocess

import pytest

from core.build_prep.assemble import build_input_for
from core.cli import main as cli_main
from core.report.data import report_data
from core.spec.ops import apply
from core.verify.run import run_verify
from tests.builder.helpers import BLENDER, build, skip_without_blender
from tests.spec.fixtures import spec_with_rooms


def _rack():
    return {"op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.0.0",
            "position": (2000, 2000, 0), "dims": (600, 1200, 2000)}


@pytest.mark.blender
@skip_without_blender
def test_blend_contains_cameras(tmp_path):
    doc, _ = build_input_for(spec_with_rooms(), None, (1000, 600))
    doc["cameras"] = [c for c in doc["cameras"] if c["name"] in ("cam_verify", "cam_top")]
    assert build(tmp_path, doc).returncode == 0
    r = subprocess.run([BLENDER, "-b", str(tmp_path / "out" / "layout.blend"), "--python-expr",
                        "import bpy; print('CAMS', sorted(o.name for o in bpy.data.objects if o.type == 'CAMERA'))"],
                       capture_output=True, text=True, timeout=120, check=False)
    assert "CAMS ['cam_top', 'cam_verify']" in r.stdout


@pytest.mark.blender
def test_corrupt_template_glb_is_skipped_with_warning(tmp_path, placeholder_root):
    root = tmp_path / "tpl"
    shutil.copytree(placeholder_root, root)
    (root / "rack-42u-600x1200" / "1.0.0" / "asset.glb").write_bytes(b"not a glb at all")
    s = apply(spec_with_rooms(), [_rack()], "editor", 2)
    doc, warnings = build_input_for(s, root, None)
    assert doc["instances"] == []
    assert len(warnings) == 1 and warnings[0].startswith("object O1: template rack-42u-600x1200@1.0.0 invalid")


def test_build_warnings_reach_verify_json_and_report(tmp_path):
    (tmp_path / "shell.glb").write_bytes(b"")  # glb check not under test here
    v = run_verify(tmp_path, spec_with_rooms(), {"meshes": []}, None,
                   extra_warnings=["object O1: template rack@9.9.9 not found"])
    assert "object O1: template rack@9.9.9 not found" in json.loads((tmp_path / "verify.json").read_text())["warnings"]
    s = apply(spec_with_rooms(), [_rack()], "editor", 2)
    data = report_data(s, v, {}, missing_objects=["O1"])
    assert data["objects"]["by_template"] == [] and any("O1" in i for i in data["issues"])


def test_cli_refuses_to_overwrite_foreign_folder(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(spec_with_rooms().model_dump_json())
    target = tmp_path / "docs"
    target.mkdir()
    (target / "keep.txt").write_text("precious")
    assert cli_main(["build", str(spec), str(target)]) == 2
    assert (target / "keep.txt").read_text() == "precious"


def test_cli_rejects_current_directory_as_out_dir(tmp_path, monkeypatch):
    spec = tmp_path / "spec.json"
    spec.write_text(spec_with_rooms().model_dump_json())
    monkeypatch.chdir(tmp_path)
    assert cli_main(["build", str(spec), "."]) == 2 and spec.exists()
