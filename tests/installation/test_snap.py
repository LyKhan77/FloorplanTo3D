import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from core.installation.snap import snap_box, snap_boxes, snap_tray

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


def test_snap_tray_on_an_upscaled_page_with_broken_band(gatsu):
    """The pipeline's page is upscaled 2x: edge lines are 4 px (about 50 mm) wide, and labels break the filled band in
    the middle, leaving only its two edges there. Both must still count (plan-37a2 smoke run)."""
    bw, t = gatsu
    big = cv2.resize(bw, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    a, b, c, d, e, f = t
    half = [a / 2, b / 2, c, d / 2, e / 2, f]
    to_px = lambda x, y: (round((x - c) / half[0]), round((y - f) / half[4]))
    for x in range(26500, 28600, 100):  # hollow the band: keep 4 px edges, clear the inside
        u, _ = to_px(x, 0)
        _, top = to_px(0, 500)
        _, bottom = to_px(0, 290)
        big[top + 3:bottom - 3, u - 4:u + 5] = 0
    r = snap_tray(big, half, [(24500, 600), (30000, 250)])
    assert r is not None and r["width"] == 200 and all(abs(p[1] - 395) <= 60 for p in r["path"])


def test_snap_boxes_finds_a_row_in_one_pass():
    """Review I8: Shift-drag over a row labels the page once and returns every rack-sized box inside the rectangle."""
    img = np.zeros((800, 800), np.uint8)
    for k in range(3):
        cv2.rectangle(img, (200 + k * 62, 300), (260 + k * 62, 420), 255, 1)
    got = snap_boxes(img, PX_TO_MM, (1500, 8000 - 2500), (4500, 8000 - 4500))
    assert len(got) == 3 and all(abs(b["size"][1] - 1200) <= 20 for b in got)
    assert snap_boxes(img, PX_TO_MM, (6000, 8000 - 6000), (7000, 8000 - 7000)) == []

