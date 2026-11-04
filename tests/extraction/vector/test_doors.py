import cv2
import numpy as np
import pytest

from core.extraction.preprocess import load_raster, preprocess
from core.extraction.vector.doors import find_doors
from tests.inputs import ANCOL, requires_ancol


def _raster_doors(r=30, n=5):
    b = np.zeros((1200, 2000), np.uint8)
    cv2.rectangle(b, (100, 100), (1900, 1100), 255, 3)
    for i in range(n):
        x = 300 + i * 300
        cv2.line(b, (x, 600), (x, 600 - r), 255, 2)
        cv2.ellipse(b, (x, 600), (r, r), 0, -90, 0, 255, 2)
    return b


def test_raster_arcs_become_doors_in_mm():
    d = find_doors(_raster_doors(), (0, 0, 2000, 1200), [30, 0, 0, 0, -30, 0])
    assert len(d) == 5
    assert d[0].radius == pytest.approx(900, rel=0.05)
    assert d[0].hinge == pytest.approx((9000, -18000), abs=60)


def test_no_arc_no_door():
    assert find_doors(_raster_doors(n=0), (0, 0, 2000, 1200), [30, 0, 0, 0, -30, 0]) == []


@requires_ancol
def test_ancol_door_count():
    r = preprocess(load_raster(ANCOL, 13), sheet=True)
    assert len(find_doors(r.binary, tuple(r.meta["drawing_bbox"]), [30.92, 0, 0, 0, -30.92, 0])) >= 35
