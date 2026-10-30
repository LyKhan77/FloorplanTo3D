import json

import cv2
import numpy as np
import pytest

from core.verify.glb_check import glb_check
from core.verify.iou import iou, plan_wall_mask
from core.verify.run import run_verify, verify_status
from tests.spec.fixtures import spec_with_rooms


def test_iou_identical_and_disjoint():
    a = np.zeros((50, 50), np.uint8)
    a[10:20, 10:40] = 255
    b = np.zeros((50, 50), np.uint8)
    b[30:40, 10:40] = 255
    assert iou(a, a) == pytest.approx(1.0) and iou(a, b) == pytest.approx(0.0)


def test_iou_tolerates_one_pixel_shift():
    a = np.zeros((50, 50), np.uint8)
    a[10:20, 10:40] = 255
    assert iou(a, np.roll(a, 1, axis=0)) > 0.8


def test_status_thresholds():
    assert verify_status(True, 0.9) == ("succeeded", [])
    status, warnings = verify_status(True, 0.8)
    assert status == "succeeded" and warnings
    assert verify_status(True, 0.6)[0] == "needs_attention" and verify_status(False, 0.95)[0] == "failed"
    assert verify_status(True, None) == ("succeeded", [])


def test_plan_mask_fills_double_line_wall():
    img = np.full((100, 200), 255, np.uint8)
    img[40, 20:180] = 0
    img[46, 20:180] = 0  # 6 px double line
    m = plan_wall_mask(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), ocr=False)
    assert (m[41:46, 50] == 255).all()


@pytest.mark.blender
def test_glb_check_passes_on_built_fixture(built_fixture_dir):
    doc = json.loads((built_fixture_dir / "build_input.json").read_text())
    r = glb_check(built_fixture_dir / "shell.glb", doc)
    assert r["pass"] and r["checked"] == 5 and r["max_err_mm"] <= 1


@pytest.mark.blender
def test_verify_without_image_skips_iou(built_fixture_dir):
    doc = json.loads((built_fixture_dir / "build_input.json").read_text())
    v = run_verify(built_fixture_dir, spec_with_rooms(), doc, None)
    assert v["iou"] is None and "no input image: IoU skipped" in v["warnings"] and v["status"] == "succeeded"
    assert json.loads((built_fixture_dir / "verify.json").read_text()) == v
    assert v["grid_check"] == {"status": "skipped"} and v["iou_threshold"] == 0.85


def fake_render(tmp_path, monkeypatch):
    """verify_top.png with a black wall band, a plan image of the same size; glb check stubbed (no Blender)."""
    import core.verify.run as run_mod

    monkeypatch.setattr(run_mod, "glb_check", lambda path, doc: {"pass": True, "max_err_mm": 0, "checked": 0})
    render = np.full((200, 300), 255, np.uint8)
    render[90:110, 20:280] = 0
    cv2.imwrite(str(tmp_path / "verify_top.png"), render)
    plan = tmp_path / "plan.png"
    cv2.imwrite(str(plan), np.full((200, 300, 3), 255, np.uint8))
    mask = tmp_path / "wall_mask.png"
    cv2.imwrite(str(mask), np.where(render < 128, 255, 0).astype(np.uint8))
    return plan, mask


def test_verify_uses_candidate_mask(tmp_path, monkeypatch):
    plan, mask = fake_render(tmp_path, monkeypatch)
    v = run_verify(tmp_path, spec_with_rooms(), {}, plan, plan_mask_path=mask)
    assert v["iou"] == 1.0 and v["mask_source"] == "candidate"


def test_imported_spec_falls_back_to_m2_mask(tmp_path, monkeypatch):
    plan, _ = fake_render(tmp_path, monkeypatch)
    v = run_verify(tmp_path, spec_with_rooms(), {}, plan)
    assert v["mask_source"] == "m2" and any("mask M2" in w for w in v["warnings"])


def test_verify_uses_mask_of_spec_run(tmp_path):
    from core.pipeline import plan_mask_for

    spec = spec_with_rooms()
    assert plan_mask_for(tmp_path, spec) is None  # imported spec: no run
    spec.meta.run_id = "r1"
    mask = tmp_path / "runs" / "r1" / "stages" / "05_validate" / "wall_mask.png"
    assert plan_mask_for(tmp_path, spec) is None  # the run left no mask
    mask.parent.mkdir(parents=True)
    mask.write_bytes(b"png")
    assert plan_mask_for(tmp_path, spec) == mask


def test_mask_follows_parent_versions_after_editor_commits(tmp_path):
    from core.pipeline import plan_mask_for
    from core.spec.store import SpecStore

    store = SpecStore(tmp_path / "specs")
    store.save_new(spec_with_rooms(), "pipeline", "r1")
    v2, _ = store.commit_ops(1, [{"op": "set_wall_height", "id": "W2", "height": 4500}], "editor")
    mask = tmp_path / "runs" / "r1" / "stages" / "05_validate" / "wall_mask.png"
    mask.parent.mkdir(parents=True)
    mask.write_bytes(b"png")
    assert v2.meta.run_id is None and plan_mask_for(tmp_path, v2) == mask


def _box(x0, y0, z0, x1, y1, z1):
    return [[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def test_expected_wall_box_rises_when_a_door_spans_the_whole_wall():
    """A door filling a gap (W215, Gatsu review) leaves only the lintel: the wall's box starts at the door head."""
    from core.verify.glb_check import expected_box
    wall = {"name": "wall_W1", "verts": _box(0, 0, 0, 1500, 150, 3000)}
    full = {"target": "wall_W1", "verts": _box(-25, -10, 0, 1525, 160, 2100)}
    part = {"target": "wall_W1", "verts": _box(100, -10, 0, 1000, 160, 2100)}
    other = {"target": "wall_W2", "verts": _box(-25, -10, 0, 1525, 160, 2100)}
    assert list(expected_box(wall, [part, other])) == [0, 0, 0, 1500, 150, 3000]
    assert list(expected_box(wall, [full])) == [0, 0, 2100, 1500, 150, 3000]
