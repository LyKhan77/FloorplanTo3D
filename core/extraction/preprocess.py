"""Stage 1 preprocess (PRD/04 tahap 1): raster/PDF, upscale, CLAHE, deskew, drawing area, Sauvola binarisation.

Later stages work in pixels of the *working* image (after upscale and deskew); `work_from_original` maps original
pixels onto it, so the final spec can keep px_to_mm relative to the original image.
"""

import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

UPSCALE_BELOW_PX = 2000
PDF_DPI = 300
SKEW_IGNORE_DEG = 0.2
SKEW_MAX_DEG = 5.0
MSG_TILTED = "Gambar miring > 5°; scan di luar cakupan"
COLOUR_SAT = 60  # HSV saturation above which a pixel is annotation colour (grid, dimensions)


@dataclass
class PreprocessResult:
    page: np.ndarray  # working grayscale
    binary: np.ndarray  # ink = 255, background = 0
    meta: dict
    status: str = "succeeded"
    message: str = ""
    warnings: list[str] = field(default_factory=list)


def load_raster(path: Path, page: int = 1) -> np.ndarray:
    """BGR image of a JPEG/PNG (alpha flattened on white) or of one PDF page rendered at 300 dpi."""
    path = Path(path)
    if path.read_bytes()[:5] == b"%PDF-":
        import pymupdf as fitz

        with fitz.open(path) as doc:
            if not 1 <= page <= doc.page_count:
                raise ValueError(f"page {page} not in 1..{doc.page_count}")
            pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(PDF_DPI / 72, PDF_DPI / 72), alpha=False)
            img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
            return cv2.cvtColor(img, cv2.COLOR_RGB2BGR if pix.n == 3 else cv2.COLOR_GRAY2BGR)
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"cannot read image {path}")
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        alpha = img[:, :, 3:4].astype(np.float32) / 255
        return (img[:, :, :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    return img


def estimate_skew(gray: np.ndarray) -> float:
    """Dominant angle (degrees, counter-clockwise positive) of long lines, folded into (-45, 45]."""
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 1800, threshold=80, minLineLength=int(0.1 * min(gray.shape)),
                            maxLineGap=5)
    if lines is None:
        return 0.0
    angles, weights = [], []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        a = math.degrees(math.atan2(-(y2 - y1), x2 - x1))
        while a > 45:
            a -= 90
        while a <= -45:
            a += 90
        angles.append(a)
        weights.append(math.hypot(x2 - x1, y2 - y1))
    order = np.argsort(angles)
    cum = np.cumsum(np.asarray(weights)[order])
    return float(np.asarray(angles)[order][np.searchsorted(cum, cum[-1] / 2)])


def deskew(gray: np.ndarray, angle: float) -> tuple[np.ndarray, np.ndarray]:
    """Rotate by -angle about the centre on an enlarged white canvas. Returns (image, 2x3 matrix)."""
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), -angle, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = math.ceil(h * sin + w * cos), math.ceil(h * cos + w * sin)
    m[0, 2] += nw / 2 - w / 2
    m[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(gray, m, (nw, nh), flags=cv2.INTER_CUBIC, borderValue=255), m


def binarize(gray: np.ndarray, k: float = 0.2, window: int = 25) -> np.ndarray:
    from skimage.filters import threshold_sauvola

    window = window if window % 2 else window + 1
    return np.where(gray < threshold_sauvola(gray, window_size=window, k=k), 255, 0).astype(np.uint8)


def drawing_bbox(binary: np.ndarray, colour: np.ndarray | None = None) -> tuple[int, int, int, int]:
    """Bbox (x0, y0, x1, y1) of the largest ink component; a paper border (>= 90% of the page) is skipped.

    colour: mask of saturated pixels. CAD exports draw grid bubbles, leaders and dimension chains in colour, and
    on a low-resolution raster they touch the building outline; without them the building stands alone.
    """
    ink = binary if colour is None else np.where(colour, 0, binary).astype(np.uint8)
    closed = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    h, w = binary.shape
    for i in sorted(range(1, n), key=lambda i: -stats[i, cv2.CC_STAT_AREA]):
        x, y, bw, bh = stats[i, :4]
        if bw * bh < 0.9 * w * h:
            return int(x), int(y), int(x + bw), int(y + bh)
    return 0, 0, w, h


def preprocess(raster_bgr: np.ndarray) -> PreprocessResult:
    gray = cv2.cvtColor(raster_bgr, cv2.COLOR_BGR2GRAY) if raster_bgr.ndim == 3 else raster_bgr
    colour = (cv2.cvtColor(raster_bgr, cv2.COLOR_BGR2HSV)[:, :, 1] > COLOUR_SAT).astype(np.uint8) * 255 \
        if raster_bgr.ndim == 3 else np.zeros_like(gray)
    oh, ow = gray.shape
    up = 2 if ow < UPSCALE_BELOW_PX else 1
    if up > 1:
        gray = cv2.resize(gray, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
        colour = cv2.resize(colour, None, fx=up, fy=up, interpolation=cv2.INTER_NEAREST)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    angle = estimate_skew(gray)
    status, message = "succeeded", ""
    rot = np.array([[1.0, 0, 0], [0, 1.0, 0]])
    if abs(angle) > SKEW_MAX_DEG:
        status, message = "needs_attention", MSG_TILTED
    elif abs(angle) > SKEW_IGNORE_DEG:
        gray, rot = deskew(gray, angle)
        colour = cv2.warpAffine(colour, rot, (gray.shape[1], gray.shape[0]), flags=cv2.INTER_NEAREST, borderValue=0)
    else:
        angle = 0.0
    binary = binarize(gray, window=25 * up)
    a = rot[:, :2] * up  # rotation after upscale
    work_from_original = [a[0, 0], a[0, 1], rot[0, 2], a[1, 0], a[1, 1], rot[1, 2]]
    meta = {"deskew_deg": round(angle, 4), "upscale": up, "work_size": [gray.shape[1], gray.shape[0]],
            "original_size": [ow, oh], "drawing_bbox": list(drawing_bbox(binary, colour > 0)),
            "work_from_original": [round(float(v), 6) for v in work_from_original]}
    return PreprocessResult(page=gray, binary=binary, meta=meta, status=status, message=message)
