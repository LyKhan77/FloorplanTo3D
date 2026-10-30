import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from core.installation.snap import snap_box, snap_tray

PX_TO_MM = [10, 0, 0, 0, -10, 8000]  # 10 mm/px, y up


@pytest.fixture(scope="module")
def gatsu():
    img = cv2.imread("floorplan/plan.jpeg", cv2.IMREAD_GRAYSCALE)
    _, bw = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return bw, json.loads(Path("benchmarks/gatsu/gt_spec.json").read_text())["meta"]["px_to_mm"]


def test_snap_tray_on_gatsu_band(gatsu):
    """The corridor band to the capacitor room: edges at about y = 500 and 290 mm, x 23800-32000."""
    bw, t = gatsu
    r = snap_tray(bw, t, [(24500, 600), (30000, 250)])
    assert r is not None and r["width"] == 200
    assert all(abs(p[1] - 395) <= 60 for p in r["path"]) and len(r["path"]) == 2


def test_snap_tray_keeps_a_corner(gatsu):
    """Two segments: the corner is where the snapped lines meet; an off-band segment keeps its drawn line."""
    bw, t = gatsu
    r = snap_tray(bw, t, [(24500, 600), (30000, 250), (30000, -3000)])
    assert r is not None and len(r["path"]) == 3 and abs(r["path"][1][1] - 395) <= 60


def test_snap_tray_without_band_returns_none():
    assert snap_tray(np.zeros((800, 800), np.uint8), PX_TO_MM, [(1000, 4000), (5000, 4000)]) is None


def blank_with_box(x0, y0, w, h):
    img = np.zeros((800, 800), np.uint8)
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), 255, 1)
    return img


def test_snap_box_finds_drawn_rack():
    img = blank_with_box(200, 300, 60, 120)  # 600 x 1200 mm, long side along y
    r = snap_box(img, PX_TO_MM, (2300, 8000 - 3600))
    assert r is not None and r["rotation"] == 0
    assert all(abs(a - b) <= 20 for a, b in zip(r["size"], (600, 1200)))
    assert abs(r["center"][0] - 2300) <= 20 and abs(r["center"][1] - (8000 - 3600)) <= 20
    turned = snap_box(blank_with_box(200, 300, 120, 60), PX_TO_MM, (2600, 8000 - 3300))
    assert turned is not None and turned["rotation"] == 90 and all(abs(a - b) <= 20 for a, b in zip(turned["size"], (600, 1200)))


def test_snap_box_ignores_huge_regions():
    img = blank_with_box(100, 100, 400, 400)  # 4000 mm room
    assert snap_box(img, PX_TO_MM, (3000, 8000 - 3000)) is None
    assert snap_box(img, PX_TO_MM, (7000, 8000 - 7000)) is None  # outside every closed region
