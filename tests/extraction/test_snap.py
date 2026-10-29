"""M8: a rough guide line snaps to the drawing's double wall line."""

import math

import cv2
import numpy as np

from core.extraction.snap import snap_wall

PX_TO_MM = [25, 0, 0, 0, -25, 10000]  # 25 mm per px, y up; 400 x 400 px page


def page(faces=(4925, 5075), x_mm=(1000, 8000)):
    img = np.zeros((400, 400), np.uint8)
    for y in faces:
        row = round((10000 - y) / 25)
        cv2.line(img, (round(x_mm[0] / 25), row), (round(x_mm[1] / 25), row), 255, 1)
    return img


def test_snaps_a_rough_line_to_the_double_line():
    a, b = (1500, 5080), (7500, 5080 + math.tan(math.radians(1.5)) * 6000)  # 80 mm off and 1.5 degrees askew
    r = snap_wall(page(), PX_TO_MM, a, b)
    assert r is not None and r["source"] == "double"
    assert all(abs(p[1] - 5000) <= 15 for p in (r["a"], r["b"]))
    assert abs(r["a"][0] - 1500) <= 30 and abs(r["b"][0] - 7500) <= 30
    assert abs(r["thickness"] - 150) <= 20


def test_no_double_line_returns_none():
    assert snap_wall(np.zeros((400, 400), np.uint8), PX_TO_MM, (1500, 5000), (7500, 5000)) is None


def test_a_single_line_snaps_with_the_default_thickness():
    """Gatsu draws some walls as one line (one face): the guide line lands on it with the default thickness."""
    r = snap_wall(page(faces=(5000,)), PX_TO_MM, (1500, 5050), (7500, 5050), default_mm=120)
    assert r is not None and r["source"] == "single" and r["thickness"] == 120
    assert all(abs(p[1] - 5000) <= 15 for p in (r["a"], r["b"]))


def test_a_double_line_beats_a_closer_stray_line():
    """Gatsu final check: the pair most samples agree on wins, not the pair nearest the rough line in one sample."""
    img = page()
    cv2.line(img, (60, round((10000 - 5150) / 25)), (100, round((10000 - 5150) / 25)), 255, 1)  # a short stray line
    r = snap_wall(img, PX_TO_MM, (1500, 5120), (7500, 5120))
    assert r is not None and r["source"] == "double" and all(abs(p[1] - 5000) <= 15 for p in (r["a"], r["b"]))
