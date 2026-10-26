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
    angle: int  # text orientation in the input image: 0 (horizontal) or 90 (vertical)
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


def _iou(a: BBox, b: BBox) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def _angle(box: BBox, text: str) -> int:
    # Orientation from the box shape; single characters are ambiguous ("1" is tall), so treat as 0.
    return 90 if len(text.strip()) >= 2 and (box[3] - box[1]) > (box[2] - box[0]) else 0


def _ocr_pass(img: np.ndarray, upscale: float, rotated_w: int | None) -> list[OcrItem]:
    result, _ = _engine()(img)
    items = []
    for points, text, score in result or []:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        box = restore_bbox((min(xs), min(ys), max(xs), max(ys)), upscale, rotated_w)
        items.append(OcrItem(text=text, bbox=box, angle=_angle(box, text), conf=float(score)))
    return items


def run_ocr(image: np.ndarray, upscale: float = 2.0) -> list[OcrItem]:
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    big = cv2.resize(image, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    rot = cv2.rotate(big, cv2.ROTATE_90_CLOCKWISE)
    # RapidOCR's angle classifier reads rotated text in both passes, so the passes overlap. On a
    # conflict, trust the pass that matches the text orientation: the 0° pass reads vertical
    # "6000" as "0009"; the rotated pass misreads single grid characters ("3" as "C").
    flat = _ocr_pass(big, upscale, None)
    rotated = _ocr_pass(rot, upscale, rot.shape[1])
    keep_flat = [f for f in flat if not any(r.angle == 90 and _iou(r.bbox, f.bbox) > 0.5 for r in rotated)]
    keep_rot = [r for r in rotated if r.angle == 90 or all(_iou(r.bbox, f.bbox) <= 0.5 for f in flat)]
    return keep_flat + keep_rot


def ocr_crop(image: np.ndarray, bbox: BBox, scale: float = 4.0) -> list[OcrItem]:
    """OCR one region enlarged `scale` times (single grid characters the page-wide pass misses)."""
    h, w = image.shape[:2]
    x0, y0 = max(0, int(bbox[0])), max(0, int(bbox[1]))
    x1, y1 = min(w, int(round(bbox[2]))), min(h, int(round(bbox[3])))
    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return []
    if crop.ndim == 2:
        crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    big = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return [OcrItem(i.text, (i.bbox[0] + x0, i.bbox[1] + y0, i.bbox[2] + x0, i.bbox[3] + y0), i.angle, i.conf)
            for i in _ocr_pass(big, scale, None)]
