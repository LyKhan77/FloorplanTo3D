import numpy as np
import pytest

from core.extraction.geometry.columns import drop_at_columns, find_columns, find_pilasters
from core.extraction.geometry.walls_s2 import _wall
from tests.extraction.geometry.synth import canvas, line

S = 13.0
AXES = [{"id": "GA", "label": "A", "orientation": "vertical", "px": 200.0},
        {"id": "G1", "label": "1", "orientation": "horizontal", "px": 150.0}]


def boxed_h(img, cx, cy, half=20):
    x0, y0, x1, y1 = cx - half, cy - half, cx + half, cy + half
    for p, q in (((x0, y0), (x1, y0)), ((x0, y1), (x1, y1)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1))):
        line(img, p, q, 2)
    line(img, (cx - 10, cy - 12), (cx + 10, cy - 12), 3)
    line(img, (cx - 10, cy + 12), (cx + 10, cy + 12), 3)
    line(img, (cx, cy - 12), (cx, cy + 12), 3)


def test_h_column_at_grid_crossing():
    img = canvas()
    boxed_h(img, 202, 148)
    cols = find_columns(img, np.zeros_like(img), AXES, [], S)
    assert len(cols) == 1
    c = cols[0]
    assert c["shape"] == "h_section" and c["grid_ref"] == ["GA", "G1"]  # axis ids (PRD/03), not labels and c["kind"] == "structural"
    assert c["size_mm"][0] == pytest.approx(520, abs=40) and c["confidence"] == pytest.approx(0.9)


def test_filled_blob_off_grid_needs_a_wall_and_a_square_shape():
    img, sym = canvas(), canvas()
    sym[300:340, 400:440] = 255  # 520 mm filled square on a wall, away from the grid
    sym[300:340, 100:140] = 255  # same square standing free in a room
    sym[200:212, 450:480] = 255  # irregular/elongated blob
    walls = [_wall("h", 320, 380, 560, 150, {})]
    cols = find_columns(img, sym, AXES, walls, S)
    assert [(round(c["center_px"][0]), c["shape"], c["confidence"]) for c in cols] == [(420, "rect", 0.5)]  # off the grid: review


def test_pilaster_on_exterior_band():
    img = canvas()
    for p, q in (((300, 40), (340, 40)), ((300, 140), (340, 140)), ((300, 40), (300, 140)), ((340, 40), (340, 140))):
        line(img, p, q, 2)  # 520 x 1300 mm hollow fin
    ext = _wall("h", 140, 100, 560, 110, {})
    ext["kind"] = "exterior"
    pil = find_pilasters(img, [ext], AXES, S)
    assert len(pil) == 1 and pil[0]["kind"] == "pilaster" and pil[0]["shape"] == "rect"
    assert pil[0]["size_mm"] == pytest.approx([520, 1300], abs=40)
    assert find_pilasters(img, [], AXES, S) == []  # no exterior wall nearby


@pytest.mark.slow
def test_gatsu_structural_columns():
    import math
    from pathlib import Path

    from core.extraction.geometry.elements import to_mm
    from core.extraction.geometry.masks import build_masks
    from core.spec.models import Spec
    from tests.extraction.geometry.gatsu import gatsu

    g = gatsu()
    m = build_masks(g["binary"], g["colour"], g["ocr"], g["meta"]["drawing_bbox"], g["s"])
    cols = find_columns(m["clean"], m["symbol"], g["grid"]["axes"], [], g["s"])
    found = [to_mm(g["grid"]["px_to_mm"], *c["center_px"]) for c in cols]
    gt = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
    structural = [c for c in gt.columns if c.kind == "structural"]
    hit = sum(any(math.dist(c.center, f) <= 300 for f in found) for c in structural)
    assert hit >= 16, (hit, len(cols))


def test_walls_inside_column_boxes_and_gap_doors_at_columns_are_dropped():
    col = {"center_px": [200.0, 150.0], "size_mm": [520, 520], "shape": "h_section", "rotation": 0, "kind": "structural",
           "confidence": 0.9, "grid_ref": ["A", "1"]}
    inside = _wall("h", 150, 185, 215, 100, {})  # the box outline read as a short wall
    real = _wall("h", 150, 230, 500, 150, {})
    doors = [{"wall": 1, "category": "door", "offset": 0, "width": 900, "door_type": "opening", "hinge": None,
              "swing": None, "confidence": 0.4, "evidence": {}},
             {"wall": 1, "category": "door", "offset": 2000, "width": 900, "door_type": "opening", "hinge": None,
              "swing": None, "confidence": 0.4, "evidence": {}}]
    walls, kept = drop_at_columns([inside, real], doors, [col], S)
    assert walls == [real]
    # door 0 starts at the column (x 230 px = 0 mm offset) -> a gap between a wall end and a column, not a doorway
    assert [d["offset"] for d in kept] == [2000] and kept[0]["wall"] == 0
