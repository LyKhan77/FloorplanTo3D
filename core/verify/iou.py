"""Top-down IoU between the rendered model and a wall mask from the plan (PRD/06 §6)."""

import cv2
import numpy as np

MIN_COMPONENT_PX = 40


def plan_wall_mask(image: np.ndarray, ocr: bool = True) -> np.ndarray:
    """Simple wall mask: ink pixels (Otsu threshold), text removed, double lines closed, thin lines opened away.

    ponytail: M2 heuristic; M5 replaces it with the chosen extraction candidate's wall mask.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    # Otsu adapts to the drawing's ink tone (JPEG wall lines are often grey, not black)
    _, dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if ocr:
        from core.extraction.ocr import run_ocr

        for item in run_ocr(image):
            x0, y0, x1, y1 = (round(v) for v in item.bbox)
            cv2.rectangle(dark, (x0 - 2, y0 - 2), (x1 + 2, y1 + 2), 0, -1)
    closed = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(opened, 8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= MIN_COMPONENT_PX
    return np.where(keep[labels], 255, 0).astype(np.uint8)


def _dilate(m: np.ndarray) -> np.ndarray:
    return cv2.dilate((m > 0).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0


def iou(render_mask: np.ndarray, plan_mask: np.ndarray) -> float:
    """|R ∩ P| / |R ∪ P| after a 1 px dilation of both, as rasterisation tolerance."""
    r, p = _dilate(render_mask), _dilate(plan_mask)
    union = np.logical_or(r, p).sum()
    return float(np.logical_and(r, p).sum() / union) if union else 0.0


def diff_image(render_mask: np.ndarray, plan_mask: np.ndarray) -> np.ndarray:
    """Green = both, red = plan only, blue = model only (BGR)."""
    r, p = render_mask > 0, plan_mask > 0
    out = np.full((*r.shape, 3), 255, np.uint8)
    out[r & p] = (0, 170, 0)
    out[p & ~r] = (0, 0, 220)
    out[r & ~p] = (220, 0, 0)
    return out
