import cv2
import pytest

from core.extraction.geometry.doors import find_doors, fit_to_walls
from core.extraction.geometry.strokes import extract_strokes
from core.extraction.geometry.walls_s2 import _wall
from tests.extraction.geometry.synth import canvas, double_wall, line

S = 12.5  # 900 mm = 72 px


def wall_with_gap(img, gap=(200, 272)):
    double_wall(img, (50, 200), (gap[0], 200))
    double_wall(img, (gap[1], 200), (550, 200))
    return [_wall("h", 200, 50, 550, 150, {"pair_overlap": 1.0, "partial_mm": 0, "gaps": [list(gap)]})]


def arc(img, center, radius, a0, a1, width=2):
    cv2.ellipse(img, center, (radius, radius), 0, a0, a1, 255, width)


def doors(img, walls, gaps=()):
    return find_doors(img, extract_strokes(img, 0, S), walls, list(gaps), S)


def test_single_swing_door_hinge_and_swing():
    img = canvas()
    walls = wall_with_gap(img)
    arc(img, (200, 200), 72, 270, 360)  # hinge at the west end of the gap, leaf swings north (left of a->b)
    line(img, (200, 200), (200, 128), 2)
    d = doors(img, walls)
    assert len(d) == 1
    d = d[0]
    assert d["door_type"] == "single_swing" and d["hinge"] == "start" and d["swing"] == "left"
    assert d["width"] == pytest.approx(900, abs=30) and d["offset"] == pytest.approx(150 * S, abs=30)
    assert d["wall"] == 0 and d["confidence"] >= 0.6


def test_hinge_end_and_swing_right():
    img = canvas()
    walls = wall_with_gap(img)
    arc(img, (272, 200), 72, 90, 180)  # hinge at the east end, swings south
    d = doors(img, walls)[0]
    assert d["hinge"] == "end" and d["swing"] == "right"


def test_double_door_from_two_facing_arcs():
    img = canvas()
    walls = wall_with_gap(img, (200, 344))  # 1800 mm
    arc(img, (200, 200), 72, 270, 360)
    arc(img, (344, 200), 72, 180, 270)
    d = doors(img, walls)
    assert len(d) == 1 and d[0]["door_type"] == "double_swing" and d[0]["hinge"] == "both"
    assert d[0]["width"] == pytest.approx(1800, abs=40)


def test_gap_without_arc_is_low_confidence_opening():
    img = canvas()
    walls = wall_with_gap(img)
    d = doors(img, walls, [{"wall_index": 0, "offset_mm": 150 * 12.5, "width_mm": 900}])
    assert len(d) == 1 and d[0]["door_type"] == "opening" and d[0]["confidence"] < 0.6


def test_arc_door_replaces_the_gap_opening():
    img = canvas()
    walls = wall_with_gap(img)
    arc(img, (200, 200), 72, 270, 360)
    d = doors(img, walls, [{"wall_index": 0, "offset_mm": 150 * 12.5, "width_mm": 900}])
    assert [x["door_type"] for x in d] == ["single_swing"]


def test_arc_outside_radius_range_rejected():
    img = canvas(800, 600)
    double_wall(img, (50, 400), (750, 400))
    walls = [_wall("h", 400, 50, 750, 150, {"pair_overlap": 1.0, "partial_mm": 0})]
    arc(img, (200, 400), 128, 270, 360)  # 1600 mm
    assert doors(img, walls) == []


def door(wall, offset, width, conf=0.8, door_type="single_swing"):
    return {"wall": wall, "category": "door", "offset": offset, "width": width, "door_type": door_type,
            "hinge": "start", "swing": "left", "confidence": conf, "evidence": {}}


def test_door_overhanging_its_wall_end_extends_the_wall_and_goes_to_review():
    # the far jamb's wall was not detected: the arc proves the doorway, so the wall runs on over it (V008)
    walls = [_wall("h", 200, 50, 200, 150, {}), _wall("v", 300, 0, 400, 150, {})]
    walls[0]["kind"] = "interior"
    out, w2 = fit_to_walls([door(0, 1800, 900), door(1, 500, 900)], walls, S)
    w, d = w2[0], out[0]
    length = (w["b"] - w["a"]) * S
    assert d["offset"] >= 50 and d["offset"] + d["width"] <= length - 50
    assert w["a"] == 50 and w["kind"] == "interior" and w["evidence"]["extended_for_door_mm"] > 0
    assert d["confidence"] < 0.6 and d["evidence"]["wall_extended"]
    assert out[1] == door(1, 500, 900) and w2[1] == walls[1]  # a door inside its wall is untouched


def test_door_before_the_wall_start_shifts_every_offset_on_that_wall():
    walls = [_wall("h", 200, 100, 400, 150, {})]
    out, w2 = fit_to_walls([door(0, -400, 900), door(0, 1500, 900)], walls, S)
    assert out[0]["offset"] >= 50 and w2[0]["a"] < 100
    assert out[1]["offset"] - out[0]["offset"] == 1900  # positions along the wall are kept


def test_overlapping_doors_on_one_wall_keep_the_more_confident():
    walls = [_wall("h", 200, 50, 550, 150, {})]
    out, _ = fit_to_walls([door(0, 1000, 900, 0.7), door(0, 1300, 900, 0.8), door(0, 3000, 900, 0.4, "opening")],
                          walls, S)
    assert [(d["offset"], d["confidence"]) for d in out] == [(1300, 0.8), (3000, 0.4)]  # V009


def test_hinge_at_a_t_junction_picks_the_wall_carrying_the_closed_leaf():
    img = canvas()
    walls = wall_with_gap(img)
    double_wall(img, (200, 40), (200, 194))  # a perpendicular wall ends at the hinge
    walls = [_wall("v", 200, 40, 200, 150, {"pair_overlap": 1.0, "partial_mm": 0})] + walls
    arc(img, (200, 200), 72, 0, 90)  # leaf closed along the horizontal wall, swings south
    d = doors(img, walls)
    assert len(d) == 1 and d[0]["wall"] == 1
