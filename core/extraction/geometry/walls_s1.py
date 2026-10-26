"""S1 solid / poche walls (PRD/04 §3.2): an opening keeps only strokes at least t_min thick; their skeleton
strokes become walls and the measured stroke width is the thickness."""

import cv2
import numpy as np

from core.extraction.geometry.strokes import extract_strokes
from core.extraction.geometry.walls_s2 import _wall

MIN_WALL_MM = 300


def solid_walls(clean: np.ndarray, symbol_mask: np.ndarray, s: float, t_min_mm: float) -> list[dict]:
    k = max(1, round(t_min_mm / s))
    solid = np.where(symbol_mask > 0, 0, clean).astype(np.uint8)
    solid = cv2.morphologyEx(solid, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    walls = []
    for x in extract_strokes(solid, 0, s):
        if x["orient"] == "o" or (x["b"] - x["a"]) * s < MIN_WALL_MM:
            continue
        w = _wall(x["orient"], x["c"], x["a"], x["b"], x["width"] * s, {"mask_density": 1.0, "partial_mm": 0})
        w["strategy"] = "S1"
        walls.append(w)
    return walls
