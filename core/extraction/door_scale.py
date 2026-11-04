"""Stage 2 fallback: the scale from door swing arcs when the plan has no dimensions (NTS sheets such as Ancol p13).

A door's swing radius is its leaf width; the median radius over the doors, set against an assumed standard leaf
(`door_leaf_width`, 800 mm by default), gives mm per working pixel.
"""

import cv2
import numpy as np
from skimage.morphology import skeletonize

from core.extraction.geometry.doors import find_arcs

MIN_DOORS = 3
STRAIGHT_RUN_FRAC = 1 / 200  # straight runs this long (share of the building's width) are walls and leaves, not arcs
# swing radius bounds as a share of the building's width (drawing bbox): scale-free, and a big sheet with a small
# plan keeps its doors (a building 6-200 m wide has doors 1/8-1/250 of it)
RADIUS_FRAC = (1 / 250, 1 / 8)
FIXTURE_SHARE = 0.6  # of the widest doors: an arc below this is a sanitary fixture (Gatsu p4: 15 px against 53 px)
LEAF_INK = 0.7  # share of the hinge-to-arc-end line that is ink: a door draws its leaf, lettering has none


def door_arcs(binary: np.ndarray, bbox: tuple[int, int, int, int]) -> list[dict]:
    """Swing arcs with a drawn leaf, in the full image's px."""
    x0, y0, x1, y1 = bbox
    crop = binary[y0:y1, x0:x1] > 0
    sk = (skeletonize(crop) * 255).astype(np.uint8)
    width = max(x1 - x0, 1)
    run = max(9, round(width * STRAIGHT_RUN_FRAC))
    straight = cv2.morphologyEx(sk, cv2.MORPH_OPEN, np.ones((1, run), np.uint8)) | \
        cv2.morphologyEx(sk, cv2.MORPH_OPEN, np.ones((run, 1), np.uint8))
    curves = np.where(cv2.dilate(straight, np.ones((5, 5), np.uint8)) > 0, 0, sk).astype(np.uint8)
    arcs = find_arcs(curves, 1.0, radius_px=(max(4.0, RADIUS_FRAC[0] * width), RADIUS_FRAC[1] * width))
    ink = cv2.dilate(crop.astype(np.uint8), np.ones((3, 3), np.uint8))
    doors = [a for a in arcs if any(_leaf_share(ink, a["center"], end) >= LEAF_INK for end in a["ends"])]
    return [{**a, "center": [a["center"][0] + x0, a["center"][1] + y0],
             "ends": [(e[0] + x0, e[1] + y0) for e in a["ends"]]} for a in doors]


def estimate_from_doors(binary: np.ndarray, bbox: tuple[int, int, int, int], leaf_mm: float) -> dict | None:
    """{"mm_per_px", "doors_used", "door_radius_px"} in working pixels, or None when fewer than MIN_DOORS doors."""
    doors = door_arcs(binary, bbox)
    if len(doors) < MIN_DOORS:
        return None
    radii = np.array([a["radius_px"] for a in doors])
    leaves = radii[radii >= FIXTURE_SHARE * np.percentile(radii, 90)]  # basins and toilets also draw small arcs
    r = float(np.median(leaves))
    return {"mm_per_px": leaf_mm / r, "doors_used": len(leaves), "door_radius_px": r}


def _leaf_share(ink: np.ndarray, centre, end) -> float:
    n = max(2, round(np.hypot(end[0] - centre[0], end[1] - centre[1])))
    xs = np.clip(np.linspace(centre[0], end[0], n).round().astype(int), 0, ink.shape[1] - 1)
    ys = np.clip(np.linspace(centre[1], end[1], n).round().astype(int), 0, ink.shape[0] - 1)
    return float(ink[ys, xs].mean())
