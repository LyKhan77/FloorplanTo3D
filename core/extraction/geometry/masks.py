"""Annotation masking before any detection (PRD/04 §3.1).

`clean` is the binary used by the detectors (`thin` also drops every thick blob, for stair detection); `symbol` and
`hatch` are kept as masks (symbols are removed from `clean`, hatch only lowers confidence later); `pointers` are the
far ends of leader lines from annotation texts.
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
SYMBOL_MAX_MM = 3000
SYMBOL_FILL_MIN = 0.5  # compact blob (Gatsu panels 0.58+); a connected wall network fills <= 0.25 of its bbox
HATCH_CELL_MM = 600
HATCH_MIN_SEGMENTS = 6
AXIS_INKED = 0.3  # share of samples with ink for an axis to count as drawn
THIN_FRAC = 0.75  # axis and dimension lines are erased only when thinner than this share of the wall stroke


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


def _symbols(clean: np.ndarray, w: float, s: float) -> tuple[np.ndarray, np.ndarray]:
    """(symbol mask, thick mask). Symbols are compact filled blobs; `thick` is every non-elongated thick blob,
    compact or not (a poche wall network, stair walls and rails), removed only from the stair-detection input."""
    k = 2 * round(w) + 1
    opened = cv2.morphologyEx(clean, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    symbol, thick = np.zeros_like(clean), np.zeros_like(clean)
    min_area, max_side = (SYMBOL_MIN_MM / s) ** 2, SYMBOL_MAX_MM / s
    for i in range(1, n):
        _, _, bw, bh, area = stats[i]
        if area >= min_area and max(bw, bh) / max(1, min(bw, bh)) < 4:
            thick[labels == i] = 255
            if max(bw, bh) <= max_side and area / (bw * bh) >= SYMBOL_FILL_MIN:
                symbol[labels == i] = 255
    # cover the blob outline that the opening shaved off
    ker = np.ones((k, k), np.uint8)
    return tuple(cv2.dilate(m, ker) if m.any() else m for m in (symbol, thick))


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


def _run(work: np.ndarray, x: int, y: int, across_x: bool) -> tuple[int, int] | None:
    """Ink run through (x, y) measured across the line: along x for a vertical line, along y for a horizontal one."""
    h, w = work.shape
    if not (0 <= x < w and 0 <= y < h) or not work[y, x]:
        return None
    lo = hi = x if across_x else y
    get = (lambda v: work[y, v]) if across_x else (lambda v: work[v, x])
    n = w if across_x else h
    while lo > 0 and get(lo - 1):
        lo -= 1
    while hi < n - 1 and get(hi + 1):
        hi += 1
    return lo, hi


def _thin_runs(work: np.ndarray, samples: list[tuple[int, int]], across_x: bool) -> list[tuple[int, int, int, int]]:
    """(x, y, lo, hi) of the ink run nearest to each sample (within 1 px across the line)."""
    out = []
    for x, y in samples:
        for d in (0, -1, 1):
            r = _run(work, x + d, y, True) if across_x else _run(work, x, y + d, False)
            if r:
                out.append((x, y, *r))
                break
    return out


def _erase(work: np.ndarray, runs, across_x: bool, max_len: float) -> None:
    for x, y, lo, hi in runs:
        if hi - lo + 1 <= max_len:
            if across_x:
                work[y, lo:hi + 1] = 0
            else:
                work[lo:hi + 1, x] = 0


def _erase_axes(work: np.ndarray, axes, w: float, bbox) -> list[str]:
    """Grid axes drawn as thin lines (§3.1.2). An axis as thick as the walls is left alone: it cannot be told
    from a wall line by width, and erasing it would cut real walls."""
    x0, y0, x1, y1 = (int(v) for v in bbox)
    h, wd = work.shape
    erased = []
    for a in sorted(axes, key=lambda a: a["id"]):
        vertical = a["orientation"] == "vertical"
        c = round(a["px"])
        span = range(max(0, y0), min(h, y1)) if vertical else range(max(0, x0), min(wd, x1))
        samples = [(c, v) if vertical else (v, c) for v in span]
        if not samples or not (0 <= c < (wd if vertical else h)):
            continue
        runs = _thin_runs(work, samples, vertical)
        if len(runs) < AXIS_INKED * len(samples):
            continue
        thick = float(np.median([hi - lo + 1 for *_, lo, hi in runs]))
        if thick > THIN_FRAC * w:
            continue
        _erase(work, runs, vertical, thick + 1)
        erased.append(a["id"])
    return erased


def _erase_dimension_lines(work: np.ndarray, texts: list[dict], w: float, pair_px: float) -> None:
    """Dimension lines: thin straight lines parallel to a dimension text, within 1.5 text heights of it."""
    dims = [t for t in texts if t.get("cls") == "dimension"]
    if not dims:
        return
    segs = _segments(work, min(min(t["bbox"][2] - t["bbox"][0], t["bbox"][3] - t["bbox"][1]) for t in dims) * 2)
    for t in dims:
        bx0, by0, bx1, by1 = t["bbox"]
        horizontal = bx1 - bx0 >= by1 - by0
        length, height = (bx1 - bx0, by1 - by0) if horizontal else (by1 - by0, bx1 - bx0)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        for seg in segs:
            sx0, sy0, sx1, sy1 = seg
            if _has_partner(seg, segs, pair_px):
                continue  # one line of a double-line wall, not a dimension line
            if horizontal and abs(sy1 - sy0) <= 1 and abs(sx1 - sx0) >= length and abs((sy0 + sy1) / 2 - cy) <= 1.5 * height \
                    and min(sx0, sx1) <= cx <= max(sx0, sx1):
                y = round((sy0 + sy1) / 2)
                runs = _thin_runs(work, [(x, y) for x in range(round(min(sx0, sx1)), round(max(sx0, sx1)) + 1)], False)
            elif not horizontal and abs(sx1 - sx0) <= 1 and abs(sy1 - sy0) >= length \
                    and abs((sx0 + sx1) / 2 - cx) <= 1.5 * height and min(sy0, sy1) <= cy <= max(sy0, sy1):
                x = round((sx0 + sx1) / 2)
                runs = _thin_runs(work, [(x, y) for y in range(round(min(sy0, sy1)), round(max(sy0, sy1)) + 1)], True)
            else:
                continue
            _erase(work, runs, not horizontal, THIN_FRAC * w)


def build_masks(binary: np.ndarray, colour: np.ndarray, ocr_items: list[dict], drawing_bbox, s: float,
                axes=()) -> dict:
    work = binary.copy()
    if colour is not None and colour.any():
        work[cv2.dilate(colour, np.ones((3, 3), np.uint8)) > 0] = 0
    margin = round(300 / s)
    x0, y0, x1, y1 = drawing_bbox
    outside = np.ones_like(work, bool)
    outside[max(0, y0 - margin):y1 + margin, max(0, x0 - margin):x1 + margin] = False
    work[outside] = 0
    texts = sorted((t for t in ocr_items if t.get("cls") != "grid_label"), key=lambda t: (t["bbox"][1], t["bbox"][0]))
    w0 = stroke_width(work)
    erased_axes = _erase_axes(work, axes, w0, drawing_bbox)
    _erase_dimension_lines(work, texts, w0, PAIR_MAX_MM / s)
    leader_segs, pointers = _leaders(work, texts, s)
    clean = work.copy()
    for t in texts:
        bx0, by0, bx1, by1 = (round(v) for v in t["bbox"])
        clean[max(0, by0 - TEXT_DILATE_PX):by1 + TEXT_DILATE_PX, max(0, bx0 - TEXT_DILATE_PX):bx1 + TEXT_DILATE_PX] = 0
    for x1_, y1_, x2_, y2_ in leader_segs:
        cv2.line(clean, (round(x1_), round(y1_)), (round(x2_), round(y2_)), 0, 3)
    w = stroke_width(clean)
    symbol, thick = _symbols(clean, w, s)
    clean[symbol > 0] = 0
    thin = np.where(thick > 0, 0, clean).astype(np.uint8)
    return {"clean": clean, "thin": thin, "symbol": symbol, "hatch": _hatch(clean, s), "pointers": pointers,
            "stroke_width": w, "erased_axes": erased_axes}
