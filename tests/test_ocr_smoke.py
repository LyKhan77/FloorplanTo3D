import math
import re
from collections import Counter

import cv2
import pytest

from core.extraction.ocr import run_ocr

GRID = Counter({c: 1 for c in "ABCDEF123"})
DIMS = Counter({"6000": 6, "4000": 1, "28000": 1, "12000": 1})  # 6000: 4 horizontal + 2 vertical
ROOMS = ["MEETING", "GUDANG", "PANTRY", "GALERY", "BATTERY", "AHU", "MDF", "CAPASITOR", "MUSHOLA"]


@pytest.mark.slow
def test_gatsu_grid_and_dimensions_readable():
    items = run_ocr(cv2.imread("floorplan/plan.jpeg"))
    found = Counter(re.sub(r"[^A-Z0-9]", "", i.text.upper()) for i in items)
    hits = sum(min(found[k], n) for k, n in (GRID + DIMS).items())
    rooms = [r for r in ROOMS if any(r in i.text.upper() for i in items)]
    print(f"grid+dim hits {hits}/18; rooms {len(rooms)}/{len(ROOMS)}: {rooms}")
    missing = {k: n - found[k] for k, n in (GRID + DIMS).items() if found[k] < n}
    print(f"missing: {missing}")
    assert hits >= math.ceil(0.9 * 18)
