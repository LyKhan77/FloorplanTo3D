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
VECTOR_MIN_PATHS = 500  # a CAD export has thousands of paths; a scan or an image-only PDF has a handful
PHOTO_MAX_PAGE_FRAC = 0.5  # a pasted photo is small; an image this big is the plan itself
FRAME_FILL_MAX = 0.06  # ink share of its bbox below which an enclosing component is the sheet frame
BLOCK_MIN_SHARE = 0.1  # a component this big against the largest is another block of the building
BLOCK_GAP = 0.03  # share of the page size; a block further than this from the building is not part of it
FRAME_SPAN = 0.8  # a component spanning this share of the page both ways carries the sheet frame
FRAME_TOL = 0.02  # share of the page size: frame lines (with the grid band) run this close to its bbox edge
SKEW_IGNORE_DEG = 0.2
SKEW_MAX_DEG = 5.0
MSG_TILTED = "Gambar miring > 5°; scan di luar cakupan"
COLOUR_SAT = 60  # HSV saturation above which a pixel is annotation colour (grid, dimensions)


@dataclass
class PreprocessResult:
    page: np.ndarray  # working grayscale
    binary: np.ndarray  # ink = 255, background = 0
    meta: dict
    colour: np.ndarray | None = None  # 255 where the pixel is annotation colour (working frame)
    status: str = "succeeded"
    message: str = ""
    warnings: list[str] = field(default_factory=list)


def _pasted_photos(page) -> list:
    """Rects of site photos pasted on a vector (CAD) plan. A scan is one big image and has few vector paths: kept."""
    if len(page.get_drawings()) < VECTOR_MIN_PATHS:
        return []
    limit = PHOTO_MAX_PAGE_FRAC * page.rect.width * page.rect.height
    return [r for img in page.get_images(full=True) for r in page.get_image_rects(img[0])
            if r.width * r.height < limit]


def load_raster(path: Path, page: int = 1) -> np.ndarray:
    """BGR image of a JPEG/PNG (alpha flattened on white) or of one PDF page rendered at 300 dpi."""
    path = Path(path)
    if path.read_bytes()[:5] == b"%PDF-":
        import pymupdf as fitz

        with fitz.open(path) as doc:
            if not 1 <= page <= doc.page_count:
                raise ValueError(f"page {page} not in 1..{doc.page_count}")
            pg = doc[page - 1]
            photos = _pasted_photos(pg)
            for r in photos:
                pg.add_redact_annot(r)
            if photos:
                # pixels, not whole images: a raster underlay under a photo keeps everything outside the photo
                pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS, graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                                    text=fitz.PDF_REDACT_TEXT_NONE)
            k = PDF_DPI / 72
            pix = pg.get_pixmap(matrix=fitz.Matrix(k, k), alpha=False)
            img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR if pix.n == 3 else cv2.COLOR_GRAY2BGR)
            for r in photos:  # the photo's frame would read as a wall
                cv2.rectangle(img, (round(r.x0 * k), round(r.y0 * k)), (round(r.x1 * k), round(r.y1 * k)),
                              (255, 255, 255), max(3, round(3 * PDF_DPI / 300)))
            return img
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"cannot read image {path}")
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        alpha = img[:, :, 3:4].astype(np.float32) / 255
        return (img[:, :, :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    return img


def pdf_thumbnails(data: bytes, width: int = 240) -> list[bytes]:
    """PNG thumbnail of every page, in order, for the page picker (photos left in: the user recognises them)."""
    if data[:5] != b"%PDF-":
        raise ValueError("not a PDF")
    import pymupdf as fitz

    with fitz.open(stream=data, filetype="pdf") as doc:
        return [pg.get_pixmap(matrix=fitz.Matrix(width / pg.rect.width, width / pg.rect.width), alpha=False)
                .tobytes("png") for pg in doc]


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


def drawing_bbox(binary: np.ndarray, colour: np.ndarray | None = None, sheet: bool = False) -> tuple[int, int, int, int]:
    """Bbox (x0, y0, x1, y1) of the building: the largest ink component and the big blocks next to it. A paper
    border (>= 90% of the page) is skipped. sheet: a CAD sheet (PDF page), where the sheet frame and its title block
    are skipped and blocks of one building are joined; a plain image is a crop, its largest component is the plan.

    colour: mask of saturated pixels. CAD exports draw grid bubbles, leaders and dimension chains in colour, and
    on a low-resolution raster they touch the building outline; without them the building stands alone.
    """
    ink = binary if colour is None else np.where(colour, 0, binary).astype(np.uint8)
    h, w = binary.shape
    stats = _components(ink)
    if not sheet:
        boxes = [(int(x), int(y), int(x + bw), int(y + bh), int(a)) for x, y, bw, bh, a in stats
                 if bw * bh < 0.9 * w * h]
        return max(boxes, key=lambda b: b[4])[:4] if boxes else (0, 0, w, h)
    # a plan cut by the sheet frame touches it: drop the frame lines and look again
    # ponytail: a frame is told from a building filling a tight crop (Gatsu, ink 0.096 of its bbox) by ink density
    # alone (Ancol p13 frame + building 0.048); a denser sheet needs a real rectangle test on the frame lines
    frames = [(x, y, x + bw, y + bh) for x, y, bw, bh, a in stats
              if bw >= FRAME_SPAN * w and bh >= FRAME_SPAN * h and bw * bh < 0.9 * w * h
              and a < FRAME_FILL_MAX * bw * bh]
    for box in frames:
        ink = _erase_frame_lines(ink, box)
    if frames:
        stats = _components(ink)
    boxes = [(int(x), int(y), int(x + bw), int(y + bh), int(a)) for x, y, bw, bh, a in stats
             if bw * bh < 0.9 * w * h]
    # a sheet frame (with its title block) encloses the building and is mostly empty paper
    boxes = sorted((b for b in boxes if not _is_frame(b, boxes, w, h)), key=lambda b: -b[4])
    if not boxes:
        return 0, 0, w, h
    # blocks of one building joined only by thin links (hatched bridges) come apart: grow over big neighbours
    big = [b for b in boxes[1:] if b[4] >= BLOCK_MIN_SHARE * boxes[0][4]]
    x0, y0, x1, y1 = boxes[0][:4]
    gap = BLOCK_GAP * max(h, w)
    grown = True
    while grown:
        grown = False
        for b in list(big):
            if b[0] - x1 <= gap and x0 - b[2] <= gap and b[1] - y1 <= gap and y0 - b[3] <= gap:
                x0, y0, x1, y1 = min(x0, b[0]), min(y0, b[1]), max(x1, b[2]), max(y1, b[3])
                big.remove(b)
                grown = True
    return x0, y0, x1, y1


def _components(ink: np.ndarray) -> np.ndarray:
    closed = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return cv2.connectedComponentsWithStats(closed, connectivity=8)[2][1:]


def _erase_frame_lines(ink: np.ndarray, box) -> np.ndarray:
    """Long straight lines running along the edges of the frame's bbox."""
    h, w = ink.shape
    tol = max(2, round(FRAME_TOL * max(h, w)))
    x0, y0, x1, y1 = box
    out = ink.copy()
    long_h = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, int(0.6 * w)), np.uint8))
    long_v = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((int(0.6 * h), 1), np.uint8))
    edges = np.zeros_like(ink)
    for y in (y0, y1):
        edges[max(0, y - tol):y + tol] |= long_h[max(0, y - tol):y + tol]
    for x in (x0, x1):
        edges[:, max(0, x - tol):x + tol] |= long_v[:, max(0, x - tol):x + tol]
    out[cv2.dilate(edges, np.ones((3, 3), np.uint8)) > 0] = 0
    return out


def _is_frame(b, boxes, w: int, h: int) -> bool:
    if b[2] - b[0] < FRAME_SPAN * w or b[3] - b[1] < FRAME_SPAN * h or \
            b[4] >= FRAME_FILL_MAX * (b[2] - b[0]) * (b[3] - b[1]):
        return False
    return any(o is not b and o[4] >= BLOCK_MIN_SHARE * b[4] and
               b[0] <= o[0] and b[1] <= o[1] and b[2] >= o[2] and b[3] >= o[3] for o in boxes)


def preprocess(raster_bgr: np.ndarray, sheet: bool = False) -> PreprocessResult:
    """sheet: the raster is a CAD sheet (a PDF page), see drawing_bbox."""
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
            "original_size": [ow, oh], "drawing_bbox": list(drawing_bbox(binary, colour > 0, sheet)),
            "work_from_original": [round(float(v), 6) for v in work_from_original]}
    return PreprocessResult(page=gray, binary=binary, meta=meta, status=status, message=message,
                            colour=np.where(colour > 0, 255, 0).astype(np.uint8))
