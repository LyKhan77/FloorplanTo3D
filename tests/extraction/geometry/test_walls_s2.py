import pytest

from core.extraction.geometry.walls_s2 import s2_walls

S = 12.5


def st(orient, c, a, b, width=4.0):
    p0, p1 = ((a, c), (b, c)) if orient == "h" else ((c, a), (c, b))
    return {"orient": orient, "c": c, "a": a, "b": b, "p0": list(p0), "p1": list(p1), "width": width}


def test_pairs_double_line_with_measured_thickness():
    w = s2_walls([st("v", 100, 50, 350), st("v", 112, 50, 350)], S, 80, 450)
    assert len(w) == 1
    assert w[0]["thickness_mm"] == pytest.approx(150, abs=13) and w[0]["c"] == pytest.approx(106)
    assert (w[0]["a"], w[0]["b"]) == (50, 350) and w[0]["strategy"] == "S2"


def test_long_line_pairs_with_several_partners():
    # partners 1875 mm apart: beyond the 1500 mm partial-pair join, so two walls on one long line
    walls = s2_walls([st("h", 100, 0, 600), st("h", 112, 0, 200), st("h", 112, 350, 600)], S, 80, 450)
    assert sorted((w["a"], w["b"]) for w in walls) == [(0, 200), (350, 600)]


def test_three_parallel_lines_pair_nearest_first():
    walls = s2_walls([st("v", 0, 0, 400), st("v", 9, 0, 400), st("v", 19, 0, 400)], S, 80, 450)
    assert [round(w["c"], 1) for w in walls] == [4.5]


def test_partial_side_missing_up_to_1500mm():
    # one side continuous 0..600 px, the other missing 1000 mm (80 px) in the middle
    walls = s2_walls([st("h", 100, 0, 600), st("h", 112, 0, 260), st("h", 112, 340, 600)], S, 80, 450)
    assert len(walls) == 1 and walls[0]["evidence"]["partial_mm"] == pytest.approx(1000, abs=15)
    assert (walls[0]["a"], walls[0]["b"]) == (0, 600)
    walls = s2_walls([st("h", 100, 0, 600), st("h", 112, 0, 220), st("h", 112, 380, 600)], S, 80, 450)  # 2000 mm
    assert len(walls) == 2


def test_thick_unpaired_line_is_partition():
    strokes = [st("v", 100, 50, 350), st("v", 112, 50, 350), st("h", 300, 100, 300, width=9.0),
               st("h", 200, 100, 300, width=4.0)]
    walls = s2_walls(strokes, S, 80, 450, default_thickness_mm=100)
    part = [w for w in walls if w["orient"] == "h"]
    assert len(part) == 1 and part[0]["c"] == 300 and part[0]["thickness_mm"] == 100
    assert part[0]["evidence"]["unpaired"] is True
