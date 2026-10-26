import cv2
import pytest

from core.extraction.geometry.doors import find_doors
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
