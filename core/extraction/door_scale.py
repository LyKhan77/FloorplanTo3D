"""Stage 2 fallback: the scale from door swing arcs when the plan has no dimensions (NTS sheets such as Ancol p13).

A door's swing radius is its leaf width; the median radius over all arcs, set against an assumed standard leaf
(`door_leaf_width`, 800 mm by default), gives mm per working pixel.
"""

import cv2
import numpy as np
from skimage.morphology import skeletonize

from core.extraction.geometry.doors import find_arcs

MIN_DOORS = 3
STRAIGHT_RUN_FRAC = 1 / 220  # straight runs this long (share of the image width) are walls, not arcs: 15 px at 3300
# swing radius bounds as a share of the image width (scale-free): lettering and small circles fall below the floor,
# which a fixed px floor would let in once a PDF is rasterised finer (Ancol p13 doors: width/127 at 300 and 600 dpi)
RADIUS_FRAC = (1 / 250, 1 / 20)


def estimate_from_doors(binary: np.ndarray, bbox: tuple[int, int, int, int], leaf_mm: float) -> dict | None:
    """{"mm_per_px", "doors_used", "door_radius_px"} in working pixels, or None when fewer than MIN_DOORS arcs."""
    x0, y0, x1, y1 = bbox
    crop = binary[y0:y1, x0:x1] > 0
    sk = (skeletonize(crop) * 255).astype(np.uint8)
    run = max(9, round(binary.shape[1] * STRAIGHT_RUN_FRAC))
    straight = cv2.morphologyEx(sk, cv2.MORPH_OPEN, np.ones((1, run), np.uint8)) | \
        cv2.morphologyEx(sk, cv2.MORPH_OPEN, np.ones((run, 1), np.uint8))
    curves = np.where(cv2.dilate(straight, np.ones((5, 5), np.uint8)) > 0, 0, sk).astype(np.uint8)
    arcs = find_arcs(curves, 1.0, radius_px=tuple(f * binary.shape[1] for f in RADIUS_FRAC))
    if len(arcs) < MIN_DOORS:
        return None
    r = float(np.median([a["radius_px"] for a in arcs]))
    return {"mm_per_px": leaf_mm / r, "doors_used": len(arcs), "door_radius_px": r}
