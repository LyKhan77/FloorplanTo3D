import cv2
import numpy as np
import pytest

import core.extraction.preprocess as pre
from core.extraction.door_scale import estimate_from_doors
from core.extraction.preprocess import load_raster, preprocess
from tests.inputs import ANCOL, requires_ancol


def _plan(doors: int, radius: int = 40) -> np.ndarray:
    """Walls with door gaps; each door is a leaf line plus a quarter-circle swing (hinge at the gap's end)."""
    b = np.zeros((900, 1200), np.uint8)
    cv2.rectangle(b, (50, 50), (1150, 850), 255, 3)
    for i in range(doors):
        hx = 150 + i * 200
        cv2.line(b, (hx - 60, 450), (hx, 450), 255, 3)
        cv2.line(b, (hx + radius, 450), (hx + 140, 450), 255, 3)
        cv2.line(b, (hx, 450), (hx, 450 - radius), 255, 2)  # open leaf
        cv2.ellipse(b, (hx, 450), (radius, radius), 0, -90, 0, 255, 2)  # swing
    return b


def test_five_doors_give_the_scale():
    r = estimate_from_doors(_plan(5), (0, 0, 1200, 900), 800)
    assert r["doors_used"] >= 5
    assert r["mm_per_px"] == pytest.approx(20, rel=0.03)
    assert r["door_radius_px"] == pytest.approx(40, rel=0.03)


def test_two_doors_are_not_enough():
    assert estimate_from_doors(_plan(2), (0, 0, 1200, 900), 800) is None


@requires_ancol
@pytest.mark.parametrize("dpi", [300, 600])
def test_ancol_p13_door_scale_near_label_scale(dpi, monkeypatch):
    monkeypatch.setattr(pre, "PDF_DPI", dpi)
    r = preprocess(load_raster(ANCOL, page=13))
    est = estimate_from_doors(r.binary, tuple(r.meta["drawing_bbox"]), 800)
    assert est["mm_per_px"] == pytest.approx(30.7 * 300 / dpi, rel=0.05)
