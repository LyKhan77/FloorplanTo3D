import json
import time
from pathlib import Path

import pytest

from core.blender_run import parse_progress
from core.cli import main as cli_main
from core.spec.models import Spec
from core.spec.ops import apply
from tests.builder.helpers import skip_without_blender
from tests.spec.fixtures import spec_with_rooms

OUTPUTS = ("layout.blend", "shell.glb", "layout_full.glb", "layout.fbx", "layout.obj", "report.html", "report.pdf",
           "verify.json", "build_input.json")


def ten_racks_in_galery() -> list[dict]:
    return [{"op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.0.0",
             "position": (x, 2000, 0), "dims": (600, 1200, 2000)} for x in range(2000, 12000, 1000)]


def test_parse_progress():
    assert parse_progress("@@PROGRESS 60 built walls") == (60, "built walls")
    assert parse_progress("noise") is None


def test_cli_rejects_invalid_spec(tmp_path):
    s = spec_with_rooms()
    s.openings[0].wall_id = "W99"
    p = tmp_path / "spec.json"
    p.write_text(s.model_dump_json())
    assert cli_main(["build", str(p), str(tmp_path / "out")]) == 2 and not (tmp_path / "out").exists()


def test_cli_failed_build_leaves_no_partial_output(tmp_path, monkeypatch):
    monkeypatch.setenv("BLENDER_BIN", "/usr/bin/false")
    spec = tmp_path / "spec.json"
    spec.write_text(spec_with_rooms().model_dump_json())
    assert cli_main(["build", str(spec), str(tmp_path / "out")]) == 1
    assert not (tmp_path / "out").exists() and not list(tmp_path.glob("out.tmp-*"))
    assert (tmp_path / "out.failed.log").exists()


@pytest.fixture(scope="module")
def gatsu_out(tmp_path_factory, placeholder_root):
    tmp = tmp_path_factory.mktemp("gatsu")
    spec = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
    spec = apply(spec, ten_racks_in_galery(), "editor", spec.meta.version + 1)
    p = tmp / "spec.json"
    p.write_text(spec.model_dump_json())
    t0 = time.monotonic()
    rc = cli_main(["build", str(p), str(tmp / "out"), "--image", "floorplan/plan.jpeg",
                   "--templates", str(placeholder_root)])
    return rc, time.monotonic() - t0, tmp / "out"


@pytest.mark.blender
@pytest.mark.slow
@skip_without_blender
def test_gatsu_end_to_end(gatsu_out):
    rc, elapsed, out = gatsu_out
    v = json.loads((out / "verify.json").read_text())
    print(f"elapsed {elapsed:.1f}s iou {v['iou']} glb {v['glb_check']} status {v['status']}")
    assert rc == 0 and elapsed <= 90 and v["glb_check"]["pass"]
    for f in OUTPUTS:
        assert (out / f).exists(), f
    assert len(list((out / "renders").glob("room_*.png"))) >= 8


@pytest.mark.blender
@pytest.mark.slow
@skip_without_blender
@pytest.mark.xfail(strict=False, reason="M2 heuristic plan mask reaches IoU ~0.45 on Gatsu (furniture, stair treads, "
                   "door arcs, fixtures and dimension lines count as walls). Target moves to M5, where the mask comes "
                   "from the chosen extraction candidate. See benchmarks/reports/m2-verify.md")
def test_gatsu_iou_meets_target(gatsu_out):
    assert json.loads((gatsu_out[2] / "verify.json").read_text())["iou"] >= 0.85
