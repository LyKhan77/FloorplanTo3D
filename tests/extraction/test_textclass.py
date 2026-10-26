from collections import Counter
from functools import cache
from pathlib import Path

import pytest

from core.extraction.ocr import OcrItem
from core.extraction.preprocess import load_raster, preprocess
from core.extraction.textclass import classify_text, ocr_page


def item(text: str) -> OcrItem:
    return OcrItem(text=text, bbox=(0, 0, 10, 10), angle=0, conf=0.9)


def test_classify_rules():
    assert classify_text(item("C"), in_circle=True, in_building=False) == "grid_label"
    assert classify_text(item("12"), in_circle=True, in_building=False) == "grid_label"
    assert classify_text(item("C"), in_circle=False, in_building=False) == "other"
    assert classify_text(item("6000"), in_circle=False, in_building=False) == "dimension"
    assert classify_text(item("28.000"), in_circle=False, in_building=False) == "dimension"
    assert classify_text(item("R. MEETING"), in_circle=False, in_building=True) == "room_label"
    assert classify_text(item("GUDANG"), in_circle=False, in_building=False) == "room_label"
    assert classify_text(item("NYY 4x1Cx185mm"), in_circle=False, in_building=True) == "annotation"
    assert classify_text(item("PROPOSED NEW PANEL SDP"), in_circle=False, in_building=True) == "proposed"
    assert classify_text(item("DISMANTLE THE WALL"), in_circle=False, in_building=True) == "dismantle"
    assert classify_text(item("NK"), in_circle=False, in_building=True) == "stair_dir"
    assert classify_text(item("MSC GATSU LANTAI 1"), in_circle=False, in_building=False) == "other"


@cache
def gatsu_classes() -> Counter:
    r = preprocess(load_raster(Path("floorplan/plan.jpeg")))
    return tuple((i.text, classify_text(i, in_circle=False, in_building=True)) for i in ocr_page(r.page, r.meta["upscale"]))


@pytest.mark.slow
def test_gatsu_page_ocr_classes():
    items = gatsu_classes()
    dims = Counter(t.replace(" ", "") for t, c in items if c == "dimension")
    expected = Counter({"6000": 6, "4000": 1, "28000": 1, "12000": 1})
    assert sum((dims & expected).values()) >= 8, dims
    rooms = " ".join(t.upper() for t, c in items if c == "room_label")
    for word in ("MEETING", "GUDANG", "PANTRY", "GALERY", "BATTERY"):
        assert word in rooms, rooms
    assert sum(c == "proposed" for _, c in items) >= 2
    assert any(c == "stair_dir" and t.strip().upper() == "NK" for t, c in items)
