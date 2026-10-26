"""Drawn line strokes (PRD/04 §3.2 S2 steps 0-2).

Strokes come from the skeleton + probabilistic Hough instead of LSD: LSD returns both edges of every 4 px line
(four segments per double-line wall on Gatsu), the skeleton one centreline per stroke.
"""

import math

import cv2
import numpy as np
from skimage.morphology import skeletonize

SNAP_DEG = 1.5
OFFSET_PX = 1.5


def directional_close(binary: np.ndarray, l_fix: int) -> np.ndarray:
    """Join breaks along lines without thickening sideways (PRD/04 §3.2 S2 step 0).

    Each direction closes only the lines of that direction (isolated by an opening 3·l_fix long): a plain
    horizontal closing would also bridge two vertical lines closer than l_fix.
    """
    if l_fix <= 0:
        return binary
    out = binary.copy()
    for along, across in (((1, l_fix), (1, 3 * l_fix)), ((l_fix, 1), (3 * l_fix, 1))):
        lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones(across, np.uint8))
        out = cv2.bitwise_or(out, cv2.morphologyEx(lines, cv2.MORPH_CLOSE, np.ones(along, np.uint8)))
    return out


def _width(dt: np.ndarray, p0, p1) -> float:
    n = max(2, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) // 3))
    h, w = dt.shape
    vals = []
    for t in np.linspace(0, 1, n):
        x, y = round(p0[0] + (p1[0] - p0[0]) * t), round(p0[1] + (p1[1] - p0[1]) * t)
        if 0 <= x < w and 0 <= y < h:
            vals.append(dt[max(0, y - 2):y + 3, max(0, x - 2):x + 3].max())
    return float(max(1.0, 2 * np.median(vals) - 1)) if vals else 1.0


def _stroke(orient: str, c: float, a: float, b: float, width: float, p0=None, p1=None) -> dict:
    if orient == "h":
        p0, p1 = (a, c), (b, c)
    elif orient == "v":
        p0, p1 = (c, a), (c, b)
    r = lambda v: round(float(v), 2)
    return {"orient": orient, "c": r(c), "a": r(a), "b": r(b), "p0": [r(p0[0]), r(p0[1])], "p1": [r(p1[0]), r(p1[1])],
            "width": r(width)}


def _merge(strokes: list[dict], max_gap: float) -> list[dict]:
    out: list[dict] = []
    for s in sorted(strokes, key=lambda s: (s["orient"], s["c"], s["a"])):
        for m in out:
            if m["orient"] == s["orient"] and abs(m["c"] - s["c"]) <= OFFSET_PX and s["a"] <= m["b"] + max_gap \
                    and s["b"] >= m["a"] - max_gap:
                la, lb = m["b"] - m["a"], s["b"] - s["a"]
                tot = max(la + lb, 1e-9)
                merged = _stroke(m["orient"], (m["c"] * la + s["c"] * lb) / tot, min(m["a"], s["a"]), max(m["b"], s["b"]),
                                 (m["width"] * la + s["width"] * lb) / tot)
                m.update(merged)
                break
        else:
            out.append(dict(s))
    return sorted(out, key=lambda s: (s["orient"], s["c"], s["a"]))


def extract_strokes(clean: np.ndarray, l_fix: int, s: float, axis_angle_deg: float = 0.0) -> list[dict]:
    sk = (skeletonize(directional_close(clean, l_fix) > 0) * 255).astype(np.uint8)
    dt = cv2.distanceTransform((clean > 0).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    w = float(max(1.0, 2 * np.median(dt[sk > 0]) - 1)) if sk.any() else 3.0
    # a skeleton retracts about w/2 at each side of a break, so a 2 px JPEG break leaves a gap of ~w + 2
    lines = cv2.HoughLinesP(sk, 1, np.pi / 360, 15, minLineLength=max(12, round(150 / s)),
                            maxLineGap=max(3, round(3 * w)))
    if lines is None:
        return []
    strokes = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4).astype(float):
        ang = (math.degrees(math.atan2(y2 - y1, x2 - x1)) - axis_angle_deg) % 180
        width = _width(dt, (x1, y1), (x2, y2))
        if min(ang, 180 - ang) <= SNAP_DEG:
            strokes.append(_stroke("h", (y1 + y2) / 2, min(x1, x2), max(x1, x2), width))
        elif abs(ang - 90) <= SNAP_DEG:
            strokes.append(_stroke("v", (x1 + x2) / 2, min(y1, y2), max(y1, y2), width))
        else:
            p0, p1 = sorted([(x1, y1), (x2, y2)])
            strokes.append(_stroke("o", 0.0, 0.0, math.hypot(x2 - x1, y2 - y1), width, p0, p1))
    straight = [x for x in strokes if x["orient"] != "o"]
    med_w = float(np.median([x["width"] for x in straight])) if straight else 3.0
    return _merge(straight, 3 * med_w) + sorted((x for x in strokes if x["orient"] == "o"), key=lambda x: (x["p0"], x["p1"]))
