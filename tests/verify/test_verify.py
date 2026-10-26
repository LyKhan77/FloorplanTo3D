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
