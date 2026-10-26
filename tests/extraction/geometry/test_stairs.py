import numpy as np
import pytest

from core.extraction.geometry.stairs import detect_stairs, find_flights, lift_boxes, stair_mask
from core.extraction.geometry.strokes import extract_strokes
from tests.extraction.geometry.synth import canvas, line, text_item

S = 12.5


def treads(img, x0, x1, y0, n, step, width=2):
    for k in range(n):
        y = round(y0 + k * step)
        line(img, (x0, y), (x1, y), width)


def test_treads_become_a_flight_not_walls():
    img = canvas(600, 500)
    treads(img, 200, 296, 80, 14, 22.4)  # 1200 mm wide, 280 mm treads
    fl = find_flights(extract_strokes(img, 0, S), S)
    assert len(fl) == 1
    f = fl[0]
    assert f["risers"] == 15 and f["width_mm"] == pytest.approx(1200, abs=25) and f["tread_axis"] == "h"
    mask = stair_mask(fl, img.shape, S)
    left = np.where(mask > 0, 0, img).astype(np.uint8)
    assert not [x for x in extract_strokes(left, 0, S) if 180 < x["p0"][0] < 320 and 60 < x["p0"][1] < 400]


def test_stair_mask_keeps_the_side_walls():
    img = canvas(600, 500)
    treads(img, 200, 296, 80, 14, 22.4)
    line(img, (194, 70), (194, 400))  # stair side wall (double line) touching the tread ends
    line(img, (182, 70), (182, 400))
    fl = find_flights(extract_strokes(img, 0, S), S)
    left = np.where(stair_mask(fl, img.shape, S) > 0, 0, img).astype(np.uint8)
    side = [x for x in extract_strokes(left, 0, S) if x["orient"] == "v" and abs(x["c"] - 194) <= 2]
    assert side and side[0]["b"] - side[0]["a"] >= 300


def test_direction_from_nk_text_and_landing_fallback():
    img = canvas(600, 600)
    treads(img, 200, 296, 150, 14, 22.4)  # flight from y=150 (north) to y=441 (south)
    nk = text_item("NK", (230, 470, 260, 485), "stair_dir")
    st, issues = detect_stairs(extract_strokes(img, 0, S), [nk], img, S)
    f = st[0]["flights"][0]
    assert f["start"][1] > f["end"][1] and st[0]["direction_source"] == "text"  # NK at the south end: going north
    # a second flight beside the first, both ending at the north landing: the text flight leads to the landing,
    # the other one leaves it
    treads(img, 400, 496, 150, 14, 22.4)
    st, issues = detect_stairs(extract_strokes(img, 0, S), [nk], img, S)
    assert len(st) == 1 and len(st[0]["flights"]) == 2 and st[0]["landings"]
    a, b = st[0]["flights"]
    assert a["start"][1] > a["end"][1] and b["start"][1] < b["end"][1]
    # no text: towards the landing, confidence 0.5
    st, issues = detect_stairs(extract_strokes(img, 0, S), [], img, S)
    assert st[0]["direction_source"] == "landing" and st[0]["confidence"] == pytest.approx(0.5)
    # a lone flight without text: unknown, 0.3 and an issue
    img2 = canvas(600, 600)
    treads(img2, 200, 296, 150, 14, 22.4)
    st, issues = detect_stairs(extract_strokes(img2, 0, S), [], img2, S)
    assert st[0]["confidence"] == pytest.approx(0.3) and [i["code"] for i in issues] == ["STAIR_DIR"]


def test_irregular_spacing_rejected():
    img = canvas(600, 500)
    ys = [80, 95, 125, 140, 175, 185, 220, 240]
    for y in ys:
        line(img, (200, y), (296, y), 2)
    assert find_flights(extract_strokes(img, 0, S), S) == []


def test_lift_box_found():
    img = canvas(600, 500)
    x0, y0, side = 200, 100, 160  # 2000 mm
    for p, q in (((x0, y0), (x0 + side, y0)), ((x0, y0 + side), (x0 + side, y0 + side)),
                 ((x0, y0), (x0, y0 + side)), ((x0 + side, y0), (x0 + side, y0 + side)),
                 ((x0, y0), (x0 + side, y0 + side)), ((x0 + side, y0), (x0, y0 + side))):
        line(img, p, q, 2)
    boxes = lift_boxes(extract_strokes(img, 0, S), S)
    assert len(boxes) == 1 and boxes[0] == pytest.approx([x0, y0, x0 + side, y0 + side], abs=6)


@pytest.mark.slow
def test_gatsu_stair_s1():
    from core.extraction.geometry.masks import build_masks
    from tests.extraction.geometry.gatsu import gatsu

    g = gatsu()
    m = build_masks(g["binary"], g["colour"], g["ocr"], g["meta"]["drawing_bbox"], g["s"])
    strokes = extract_strokes(m["clean"], 0, g["s"])
    texts = [i for i in g["ocr"] if i["cls"] == "stair_dir"]
    st, _ = detect_stairs(strokes, texts, m["clean"], g["s"])
    s1 = [f for s in st for f in s["flights"] if 410 <= f["start"][0] <= 840 and 360 <= f["start"][1] <= 760]
    assert len(s1) >= 2, st
    east = max(s1, key=lambda f: f["start"][0])
    west = min(s1, key=lambda f: f["start"][0])
    assert west["risers"] == pytest.approx(15, abs=1)
    # the east flight's lowest treads are cut by the walking line and the axis-2 line: 13 of 15 risers found
    assert east["risers"] >= 12
    assert east["start"][1] > east["end"][1]  # naik ke utara (NK + walking line at the south end)
    assert west["start"][1] < west["end"][1]  # leaves the north landing towards the south
    boxes = lift_boxes(strokes, g["s"])
    assert any(abs((b[0] + b[2]) / 4 - 300) <= 25 and abs((b[1] + b[3]) / 4 - 250) <= 25 for b in boxes), boxes
