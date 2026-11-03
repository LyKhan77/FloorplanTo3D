import json

import cv2
import numpy as np
import pytest

from core.extraction.geometry import masks
from core.extraction.geometry.trays import TRAY_STYLES, tray_mask
from core.extraction.stages import stage_extract
from tests.extraction.test_stages import make_project, run_0_2
from tests.inputs import ANCOL, requires_ancol

S = 15.0  # mm per px
STROKE = 3


def _ladder(img: np.ndarray, style: dict, x0: int, y0: int, length_mm: float, vertical: bool = False) -> None:
    """A tray as CAD draws it: two rails and rungs at a fixed pitch (drawn horizontally, then transposed)."""
    w, pitch, rung = (round(style[k] / S) for k in ("width", "pitch", "rung"))
    n = round(length_mm / S)
    t = np.zeros((w + STROKE, n), np.uint8)
    cv2.line(t, (0, 0), (n, 0), 255, STROKE)
    cv2.line(t, (0, w), (n, w), 255, STROKE)
    for x in range(0, n - rung, pitch):
        cv2.rectangle(t, (x, 0), (x + rung, w), 255, -1)
    t = t.T if vertical else t
    img[y0:y0 + t.shape[0], x0:x0 + t.shape[1]] |= t


@pytest.mark.parametrize("name", list(TRAY_STYLES))
def test_drawn_ladder_is_masked(name):
    img = np.zeros((800, 800), np.uint8)
    _ladder(img, TRAY_STYLES[name], 50, 100, 9000)
    _ladder(img, TRAY_STYLES[name], 100, 200, 8000, vertical=True)
    m = tray_mask(img, S, STROKE)
    assert ((m > 0) & (img > 0)).sum() / (img > 0).sum() > 0.9


def test_walls_are_not_trays():
    img = np.zeros((800, 800), np.uint8)
    cv2.line(img, (50, 100), (750, 100), 255, STROKE)  # double-line wall, 150 mm
    cv2.line(img, (50, 110), (750, 110), 255, STROKE)
    cv2.rectangle(img, (50, 300), (750, 313), 255, -1)  # filled wall, 200 mm
    cv2.rectangle(img, (100, 450), (700, 750), 255, STROKE)  # a room
    assert tray_mask(img, S, STROKE).sum() == 0


@requires_ancol
@pytest.mark.slow
def test_ancol_p13_columns_drop(tmp_path, monkeypatch):
    def columns(name: str) -> int:
        project = make_project(tmp_path / name, ANCOL.read_bytes(), "pdf", page=13)
        stages, _ = run_0_2(project)
        assert stage_extract(project, stages / "03_extract", 1)["status"] == "succeeded"
        assert (stages / "03_extract" / "masks" / "tray.png").is_file()
        return json.loads((stages / "03_extract" / "candidates.json").read_text())[0]["counts"]["columns"]

    with_trays = columns("masked")
    monkeypatch.setattr(masks, "tray_mask", lambda img, s, w: np.zeros_like(img))
    without = columns("unmasked")
    assert with_trays <= 0.8 * without, (with_trays, without)  # tray rungs were read as columns


def test_short_ladder_like_pattern_is_not_a_tray():
    # a stair flight end or leaders crossing a wall can look like a few rungs; a tray runs for metres
    img = np.zeros((800, 800), np.uint8)
    _ladder(img, TRAY_STYLES["ladder_wide"], 50, 100, 1200)
    assert tray_mask(img, S, STROKE).sum() == 0
