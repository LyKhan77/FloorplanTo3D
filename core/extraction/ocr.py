"""Global OCR (PRD/04-extraction.md §2.1): RapidOCR on the upscaled image, plus a 90° pass for vertical text."""

from dataclasses import dataclass
from functools import cache

import cv2
import numpy as np

BBox = tuple[float, float, float, float]  # x0, y0, x1, y1


@dataclass(frozen=True)
class OcrItem:
    text: str
    bbox: BBox  # pixels of the input image
    angle: int  # 0 or 90
    conf: float


def restore_bbox(bbox: BBox, upscale: float, rotated_w: int | None = None) -> BBox:
    """Map a bbox from the working image back to input pixels.

    rotated_w: width of the working image when it was rotated 90° clockwise (cv2.ROTATE_90_CLOCKWISE).
    """
    x0, y0, x1, y1 = bbox
    if rotated_w is not None:
        # rotated (xr, yr) comes from unrotated (x, y) = (yr, rotated_w - xr)
        x0, y0, x1, y1 = y0, rotated_w - x1, y1, rotated_w - x0
    return (x0 / upscale, y0 / upscale, x1 / upscale, y1 / upscale)


@cache
def _engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _ocr_pass(img: np.ndarray, upscale: float, rotated_w: int | None, angle: int) -> list[OcrItem]:
    result, _ = _engine()(img)
    items = []
    for points, text, score in result or []:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        box = restore_bbox((min(xs), min(ys), max(xs), max(ys)), upscale, rotated_w)
        items.append(OcrItem(text=text, bbox=box, angle=angle, conf=float(score)))
    return items


def run_ocr(image: np.ndarray, upscale: float = 2.0) -> list[OcrItem]:
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    big = cv2.resize(image, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    rot = cv2.rotate(big, cv2.ROTATE_90_CLOCKWISE)
    # ponytail: no dedup between passes; text classification in M5 filters noise
    return _ocr_pass(big, upscale, None, 0) + _ocr_pass(rot, upscale, rot.shape[1], 90)
