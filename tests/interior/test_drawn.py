import itertools

import cv2
import numpy as np
import pytest

from core.installation.snap import snap_box
from core.interior.drawn import place_drawn
from core.interior.library import load_library
from core.interior.rules import load_rules
from core.interior.space import room_space
from tests.interior.conftest import hall

RACK = "rack-42u-600x1200"
R = load_rules()


@pytest.fixture(scope="module")
def lib(library_dir):
    return load_library(library_dir)


def box(cx, cy, short, long, rot=0, bid="K1"):
    return {"id": bid, "center": [cx, cy], "size": [short, long], "rotation": rot}


def test_one_box_one_object(lib):
    ps, notes = place_drawn([box(3000, 3000, 620, 1160)], lib[RACK], None, R)
    (p,) = ps
    assert (round(p.x), round(p.y), p.source) == (3000, 3000, "drawing") and notes == []


def test_row_box_splits(lib):
    """A row of 8 racks is drawn 1200 deep x 4800 long: split into racks side by side along the long side."""
    ps, _ = place_drawn([box(3000, 3000, 1200, 4800)], lib[RACK], None, R)
    assert len(ps) == 8
    ys = sorted(p.y for p in ps)
    assert all(b - a == pytest.approx(600) for a, b in itertools.pairwise(ys)) and all(p.x == pytest.approx(3000) for p in ps)


def test_far_off_size_keeps_the_template_and_notes(lib):
    ps, notes = place_drawn([box(3000, 3000, 900, 900)], lib[RACK], None, R)
    assert ps[0].dims[:2] == (600, 1200) and any("K1" in n for n in notes)


def test_front_faces_the_open_side(lib):
    spec = hall(w=8000, h=6000)
    sp = room_space(spec, spec.rooms[0].id, None, 3000, lib, R)
    # a rack drawn with its long side (depth) along x, back against the west wall: it can only face east
    ps, notes = place_drawn([box(100 + 600 + 1, 3000, 600, 1200, rot=90)], lib[RACK], sp, R)
    (p,) = ps
    assert p.front()[0] == pytest.approx(1, abs=1e-6) and notes == []
    # mid-room with its depth along y: both sides are open -> a note that the front is uncertain
    _, notes = place_drawn([box(4000, 3000, 600, 1200, rot=0)], lib[RACK], sp, R)
    assert any("arah depan K1" in n for n in notes)


def test_snap_box_allows_a_row_when_asked():
    img = np.zeros((800, 800), np.uint8)
    cv2.rectangle(img, (200, 100), (320, 580), 255, 1)  # 1200 x 4800 mm at 10 mm/px
    t = [10, 0, 0, 0, -10, 8000]
    at = (2600, 8000 - 3400)
    assert snap_box(img, t, at) is None
    r = snap_box(img, t, at, max_mm=20000)
    assert r is not None and abs(r["size"][1] - 4800) <= 30 and abs(r["size"][0] - 1200) <= 30 and r["rotation"] == 0
