"""Annotation masking before any detection (PRD/04 §3.1).

`clean` is the binary used by the detectors; `symbol` and `hatch` are kept as masks (symbols are removed from
`clean`, hatch only lowers confidence later); `pointers` are the far ends of leader lines from annotation texts.
"""

import math

import cv2
import numpy as np
from skimage.morphology import skeletonize

LEADER_CLASSES = ("annotation", "proposed", "dismantle")
TEXT_DILATE_PX = 2
LEADER_TOUCH_PX = 6
LEADER_MIN_MM = 300
LEADER_MAX_MM = 6000
PAIR_MAX_MM = 450  # a line with a parallel partner this close is one side of a double-line wall, not a leader
SYMBOL_MIN_MM = 300
HATCH_CELL_MM = 600
HATCH_MIN_SEGMENTS = 6


def _skeleton(binary: np.ndarray) -> np.ndarray:
    return (skeletonize(binary > 0) * 255).astype(np.uint8)


def stroke_width(binary: np.ndarray) -> float:
    """Median drawn line width (px): 2·d − 1 with d the exact distance to background along the skeleton."""
    sk = _skeleton(binary) > 0
    if not sk.any():
        return 1.0
    dt = cv2.distanceTransform((binary > 0).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    return float(max(1.0, np.median(dt[sk]) * 2 - 1))


def _segments(binary: np.ndarray, min_len: float) -> np.ndarray:
    lines = cv2.HoughLinesP(_skeleton(binary), 1, np.pi / 360, 15, minLineLength=max(5, int(min_len)), maxLineGap=3)
    return np.zeros((0, 4)) if lines is None else lines.reshape(-1, 4).astype(float)


def _dist_to_box(x: float, y: float, box) -> float:
    dx = max(box[0] - x, 0, x - box[2])
    dy = max(box[1] - y, 0, y - box[3])
    return math.hypot(dx, dy)


def _has_partner(seg, segs: np.ndarray, max_gap: float) -> bool:
    x1, y1, x2, y2 = seg
    length = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    for a1, b1, a2, b2 in segs:
        l2 = math.hypot(a2 - a1, b2 - b1)
        if l2 == 0 or abs(((a2 - a1) * uy - (b2 - b1) * ux) / l2) > math.sin(math.radians(3)):
            continue  # not parallel
        gap = abs((a1 - x1) * uy - (b1 - y1) * ux)
        if gap < 2 or gap > max_gap:
            continue
        t1, t2 = sorted(((a1 - x1) * ux + (b1 - y1) * uy, (a2 - x1) * ux + (b2 - y1) * uy))
        if min(t2, length) - max(t1, 0) >= 0.6 * min(length, l2):
            return True
    return False


def _leaders(work: np.ndarray, texts: list[dict], s: float) -> tuple[list[tuple], list[dict]]:
    segs, pointers = [], []
    targets = [t for t in texts if t.get("cls") in LEADER_CLASSES]
    if not targets:
        return segs, pointers
    all_segs = _segments(work, LEADER_MIN_MM / s)
    for seg in all_segs:
        x1, y1, x2, y2 = seg
        if math.hypot(x2 - x1, y2 - y1) > LEADER_MAX_MM / s:
            continue
        for t in targets:
            d1, d2 = _dist_to_box(x1, y1, t["bbox"]), _dist_to_box(x2, y2, t["bbox"])
            if min(d1, d2) <= LEADER_TOUCH_PX and max(d1, d2) > LEADER_TOUCH_PX:
                if _has_partner(seg, all_segs, PAIR_MAX_MM / s):
                    break  # a wall line ending next to a text
                far = (x2, y2) if d1 <= d2 else (x1, y1)
                segs.append((x1, y1, x2, y2))
                pointers.append({"cls": t["cls"], "text_bbox": list(t["bbox"]), "point": [round(far[0], 1), round(far[1], 1)]})
                break
    pointers.sort(key=lambda p: (p["point"][1], p["point"][0], p["cls"]))
    return segs, pointers


def _symbols(clean: np.ndarray, w: float, s: float) -> np.ndarray:
    k = 2 * round(w) + 1
    opened = cv2.morphologyEx(clean, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    mask = np.zeros_like(clean)
    min_area = (SYMBOL_MIN_MM / s) ** 2
    for i in range(1, n):
        _, _, bw, bh, area = stats[i]
        if area >= min_area and max(bw, bh) / max(1, min(bw, bh)) < 4:
            mask[labels == i] = 255
    # cover the blob outline that the opening shaved off
    return cv2.dilate(mask, np.ones((k, k), np.uint8)) if mask.any() else mask


def _hatch(clean: np.ndarray, s: float) -> np.ndarray:
    cell = max(4, round(HATCH_CELL_MM / s))
    h, w = clean.shape
    gh, gw = math.ceil(h / cell), math.ceil(w / cell)
    angles: dict[tuple[int, int], list[float]] = {}
    for x1, y1, x2, y2 in _segments(clean, 3):
        if math.hypot(x2 - x1, y2 - y1) >= cell:
            continue
        key = (int((y1 + y2) / 2 // cell), int((x1 + x2) / 2 // cell))
        angles.setdefault(key, []).append(math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180)
    grid = np.zeros((gh, gw), np.uint8)
    for (r, c), angs in angles.items():
        ref = float(np.median(angs))
        parallel = sum(min(abs(a - ref), 180 - abs(a - ref)) <= 10 for a in angs)
        if parallel >= HATCH_MIN_SEGMENTS:
            grid[r, c] = 255
    grid = cv2.morphologyEx(grid, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return cv2.resize(grid, (gw * cell, gh * cell), interpolation=cv2.INTER_NEAREST)[:h, :w]


def build_masks(binary: np.ndarray, colour: np.ndarray, ocr_items: list[dict], drawing_bbox, s: float) -> dict:
    work = binary.copy()
    if colour is not None and colour.any():
        work[cv2.dilate(colour, np.ones((3, 3), np.uint8)) > 0] = 0
    margin = round(300 / s)
    x0, y0, x1, y1 = drawing_bbox
    outside = np.ones_like(work, bool)
    outside[max(0, y0 - margin):y1 + margin, max(0, x0 - margin):x1 + margin] = False
    work[outside] = 0
    texts = sorted((t for t in ocr_items if t.get("cls") != "grid_label"), key=lambda t: (t["bbox"][1], t["bbox"][0]))
    leader_segs, pointers = _leaders(work, texts, s)
    clean = work.copy()
    for t in texts:
        bx0, by0, bx1, by1 = (round(v) for v in t["bbox"])
        clean[max(0, by0 - TEXT_DILATE_PX):by1 + TEXT_DILATE_PX, max(0, bx0 - TEXT_DILATE_PX):bx1 + TEXT_DILATE_PX] = 0
    for x1_, y1_, x2_, y2_ in leader_segs:
        cv2.line(clean, (round(x1_), round(y1_)), (round(x2_), round(y2_)), 0, 3)
    w = stroke_width(clean)
    symbol = _symbols(clean, w, s)
    clean[symbol > 0] = 0
    return {"clean": clean, "symbol": symbol, "hatch": _hatch(clean, s), "pointers": pointers, "stroke_width": w}
