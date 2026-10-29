"""Guide-line snap (M8 review): a rough line a person drew over a missed wall lands on the drawing's double line.

Along the rough line, every SAMPLE_MM a profile across it looks for two ink runs (the wall's two faces) 60-400 mm
apart, the pair nearest the rough line. Enough samples must agree; their face midpoints give the centreline (a
least-squares fit, so a slightly askew rough line still lands straight) and their spacing the thickness.
"""

import math

import numpy as np

from core.extraction.rooms.overlay import px_from_mm

SAMPLE_MM = 100
FACE_MIN_MM, FACE_MAX_MM = 60, 400
MIN_AGREE = 0.6


def _runs(ink: np.ndarray, offsets: np.ndarray) -> list[float]:
    """Centre offset of every run of ink along the profile."""
    out, start = [], None
    for i, v in enumerate(ink):
        if v and start is None:
            start = i
        if not v and start is not None:
            out.append(float(offsets[start:i].mean()))
            start = None
    if start is not None:
        out.append(float(offsets[start:].mean()))
    return out


def snap_wall(binary: np.ndarray, px_to_mm: list[float], a, b, search_mm: float = 400) -> dict | None:
    """{"a", "b", "thickness"} in mm, or None when no double line runs along the rough line."""
    length = math.dist(a, b)
    if length < SAMPLE_MM:
        return None
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    nx, ny = -uy, ux
    to_px = px_from_mm(px_to_mm)
    step = abs(px_to_mm[0]) / 2 or 1.0  # half a pixel along the profile
    offsets = np.arange(-search_mm, search_mm + step, step)
    h, w = binary.shape[:2]
    n = max(2, int(length // SAMPLE_MM))
    mids, seps = [], []
    for k in range(n + 1):
        c = (a[0] + ux * length * k / n, a[1] + uy * length * k / n)
        ink = np.zeros(len(offsets), bool)
        for i, o in enumerate(offsets):
            x, y = to_px(c[0] + nx * o, c[1] + ny * o)
            xi, yi = round(x), round(y)
            ink[i] = 0 <= xi < w and 0 <= yi < h and binary[yi, xi] > 0
        runs = _runs(ink, offsets)
        pairs = [(abs((p + q) / 2), (p + q) / 2, q - p) for i, p in enumerate(runs) for q in runs[i + 1:]
                 if FACE_MIN_MM <= q - p <= FACE_MAX_MM]
        if pairs:
            _, mid, sep = min(pairs)
            mids.append((c[0] + nx * mid, c[1] + ny * mid))
            seps.append(sep)
    if len(mids) < MIN_AGREE * (n + 1):
        return None
    pts = np.array(mids)
    centre = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - centre)
    d = vt[0] if vt[0] @ np.array([ux, uy]) >= 0 else -vt[0]
    pa, pb = (centre + d * ((np.array(p, float) - centre) @ d) for p in (a, b))
    return {"a": [round(float(v)) for v in pa], "b": [round(float(v)) for v in pb],
            "thickness": int(round(float(np.median(seps)) / 10) * 10)}
