"""Synthetic plan drawing helpers for stage-3 unit tests (ink = 255 on 0)."""

import cv2
import numpy as np


def canvas(w: int = 600, h: int = 400) -> np.ndarray:
    return np.zeros((h, w), np.uint8)


def line(img, p, q, width: int = 4) -> None:
    cv2.line(img, (int(p[0]), int(p[1])), (int(q[0]), int(q[1])), 255, width)


def double_wall(img, p, q, gap_px: float = 12, width: int = 4) -> None:
    """Two parallel lines whose centres are gap_px apart, around the centreline p-q (axis-aligned)."""
    (x0, y0), (x1, y1) = p, q
    h = gap_px / 2
    if y0 == y1:
        line(img, (x0, y0 - h), (x1, y1 - h), width)
        line(img, (x0, y0 + h), (x1, y1 + h), width)
    else:
        line(img, (x0 - h, y0), (x1 - h, y1), width)
        line(img, (x0 + h, y0), (x1 + h, y1), width)


def room(img, x0, y0, x1, y1, gap_px: float = 12) -> None:
    double_wall(img, (x0, y0), (x1, y0), gap_px)
    double_wall(img, (x0, y1), (x1, y1), gap_px)
    double_wall(img, (x0, y0), (x0, y1), gap_px)
    double_wall(img, (x1, y0), (x1, y1), gap_px)


def text_item(text: str, bbox, cls: str) -> dict:
    return {"text": text, "bbox": list(bbox), "angle": 0, "conf": 0.9, "cls": cls}
