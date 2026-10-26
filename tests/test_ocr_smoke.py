import math
import re
from collections import Counter
from functools import cache

import cv2
import pytest

from core.extraction.ocr import run_ocr

GRID = Counter({c: 1 for c in "ABCDEF123"})
DIMS = Counter({"6000": 6, "4000": 1, "28000": 1, "12000": 1})  # 6000: 4 horizontal + 2 vertical
ROOMS = ["MEETING", "GUDANG", "PANTRY", "GALERY", "BATTERY", "AHU", "MDF", "CAPASITOR", "MUSHOLA"]

pytestmark = pytest.mark.slow


@cache
def gatsu_items():
    return tuple(run_ocr(cv2.imread("floorplan/plan.jpeg")))


def norm(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


@pytest.mark.xfail(
    strict=False,
    reason="M0: 16/18 after dedup; single-char grid bubbles 'C' and '1' unread at upscale 2-3. "
    "M5 grid detection OCRs each bubble crop (PRD 04 §2.2). See benchmarks/reports/m0-smoke.md",
)
def test_gatsu_grid_and_dimensions_readable():
    found = Counter(norm(i.text) for i in gatsu_items())
    hits = sum(min(found[k], n) for k, n in (GRID + DIMS).items())
    missing = {k: n - found[k] for k, n in (GRID + DIMS).items() if found[k] < n}
    print(f"grid+dim hits {hits}/18; missing: {missing}")
    assert hits >= math.ceil(0.9 * 18)


def test_gatsu_room_labels_readable():
    rooms = [r for r in ROOMS if any(r in i.text.upper() for i in gatsu_items())]
    assert len(rooms) >= 8, rooms


def test_gatsu_vertical_dimensions_read_by_rotated_pass():
    vertical = Counter(norm(i.text) for i in gatsu_items() if i.angle == 90)
    assert vertical["6000"] >= 2 and vertical["12000"] >= 1


def test_rotated_pass_has_no_horizontal_duplicates():
    items = gatsu_items()
    rotated = [i for i in items if i.angle == 90]
    flat = [i for i in items if i.angle == 0]
    wide = [i.text for i in rotated if (i.bbox[2] - i.bbox[0]) > (i.bbox[3] - i.bbox[1])]
    dups = [r.text for r in rotated if any(iou(r.bbox, f.bbox) > 0.5 for f in flat)]
    assert wide == [] and dups == []
