"""Snap traced installation items to the drawing (design §6.3, §6.3b).

Tray: along each rough segment, a profile across it every SAMPLE_MM lists the ink runs. A tray band is either one wide
run (a band drawn filled or hatched, as in Gatsu) or two thin runs (its edge lines); the candidate is its centre and its
outer width. A wide run never pairs with a line beside it: that pair would be the band plus a neighbouring line. The candidate most samples agree on wins (the vote of core/extraction/snap.py), and the agreed centres
are fitted along the segment. The tray width is the band's outer width less one drawn line, rounded to a standard size.

Box: the smallest closed region of paper (4-connected background) around the click, when it is rack-sized.
"""

import itertools
import math

import cv2
import numpy as np

from core.extraction.rooms.overlay import px_from_mm
from core.extraction.snap import MIN_AGREE, _vote
from core.installation.models import TRAY_WIDTHS

SAMPLE_MM = 100
SEARCH_MM = 400
BAND_MIN_MM, BAND_MAX_MM = 80, 700
ASKEW = math.tan(math.radians(5))  # a traced tray segment may be this far off the band (walls: 2 degrees)
BOX_MIN_MM, BOX_MAX_MM = 300, 3000


def _runs(ink: np.ndarray, offsets: np.ndarray) -> list[tuple[float, float]]:
    """(start, end) offset of every run of ink along the profile."""
    out, start = [], None
    for i, v in enumerate(ink):
        if v and start is None:
            start = i
        if not v and start is not None:
            out.append((float(offsets[start]), float(offsets[i - 1])))
            start = None
    if start is not None:
        out.append((float(offsets[start]), float(offsets[-1])))
    return out


def _snap_segment(binary, to_px, step: float, a, b) -> tuple[tuple, tuple, list[float], list[float]] | None:
    """Snapped (a, b) of one segment, the agreed band widths and the thin line widths seen; None without a band."""
    length = math.dist(a, b)
    if length < SAMPLE_MM:
        return None
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    nx, ny = -uy, ux
    offsets = np.arange(-SEARCH_MM, SEARCH_MM + step, step)
    h, w = binary.shape[:2]
    n = max(2, int(length // SAMPLE_MM))
    samples, thin = [], []
    for k in range(n + 1):
        t = length * k / n
        cx, cy = a[0] + ux * t, a[1] + uy * t
        ink = np.zeros(len(offsets), bool)
        for i, o in enumerate(offsets):
            x, y = to_px(cx + nx * o, cy + ny * o)
            xi, yi = round(x), round(y)
            ink[i] = 0 <= xi < w and 0 <= yi < h and binary[yi, xi] > 0
        runs = _runs(ink, offsets)
        thin += [e - s + step for s, e in runs if e - s + step < BAND_MIN_MM]  # drawn lines, in mm: pages are upscaled
        cands = [((s + e) / 2, e - s + step) for s, e in runs if BAND_MIN_MM <= e - s + step <= BAND_MAX_MM]
        edges = [r for r in runs if r[1] - r[0] + step < BAND_MIN_MM]  # a wide run is a band, not an edge
        cands += [((edges[i][0] + edges[j][1]) / 2, edges[j][1] - edges[i][0] + step)
                  for i in range(len(edges)) for j in range(i + 1, len(edges))
                  if BAND_MIN_MM <= edges[j][1] - edges[i][0] + step <= BAND_MAX_MM]
        samples.append((t, cands))
    picked = _vote(samples, MIN_AGREE * (n + 1), ASKEW)
    if picked is None:
        return None
    ts = np.array([t for t, _ in picked])
    mids = np.array([c[0] for _, c in picked])
    beta, alpha = np.polyfit(ts, mids, 1) if len(ts) > 2 else (0.0, float(np.median(mids)))
    if abs(beta) > ASKEW:  # agreed centres that drift more than 2 degrees are not one straight band
        return None
    end = lambda t: (a[0] + ux * t + nx * (alpha + beta * t), a[1] + uy * t + ny * (alpha + beta * t))
    return end(0.0), end(length), [c[1] for _, c in picked], thin


def _meet(p1, p2, q1, q2):
    """Intersection of the lines p1-p2 and q1-q2, or None when they are (nearly) parallel."""
    d1, d2 = (p2[0] - p1[0], p2[1] - p1[1]), (q2[0] - q1[0], q2[1] - q1[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-6 * math.hypot(*d1) * math.hypot(*d2):
        return None
    t = ((q1[0] - p1[0]) * d2[1] - (q1[1] - p1[1]) * d2[0]) / den
    return (p1[0] + d1[0] * t, p1[1] + d1[1] * t)


def snap_tray(binary: np.ndarray, px_to_mm: list[float], points: list) -> dict | None:
    """{"path": [[x, y], ...], "width": standard mm}; segments with no band keep their drawn line; None if none snaps."""
    to_px = px_from_mm(px_to_mm)
    step = abs(px_to_mm[0]) / 2 or 1.0  # half a pixel along the profile
    pts = [tuple(p) for p in points]
    snapped = [_snap_segment(binary, to_px, step, p, q) for p, q in itertools.pairwise(pts)]
    if not any(snapped):
        return None
    lines = [(s[0], s[1]) if s else seg for s, seg in zip(snapped, itertools.pairwise(pts), strict=True)]
    widths = [x for s in snapped if s for x in s[2]]
    thin = [x for s in snapped if s for x in s[3]]
    line_mm = float(np.median(thin)) if thin else step * 2
    width = min(TRAY_WIDTHS, key=lambda v: abs(v - (float(np.median(widths)) - line_mm)))
    path = [lines[0][0]]
    for (p1, p2), (q1, q2), orig in zip(lines, lines[1:], pts[1:-1]):
        path.append(_meet(p1, p2, q1, q2) or orig)
    path.append(lines[-1][1])
    return {"path": [[round(x), round(y)] for x, y in path], "width": width}


def _box(stats_row, px_to_mm: list[float], w: int, h: int) -> dict | None:
    """A closed paper region (connected-component stats) as a rack box in mm, or None when open or not rack-sized."""
    x, y, bw, bh, _ = (int(v) for v in stats_row)
    if x == 0 or y == 0 or x + bw >= w or y + bh >= h:  # open to the page edge: not a closed box
        return None
    a, b, c, d, e, f = px_to_mm
    sx, sy = math.hypot(a, d), math.hypot(b, e)
    size_x, size_y = (bw + 1) * sx, (bh + 1) * sy  # the inside plus half a line on each side
    if not (BOX_MIN_MM <= min(size_x, size_y) and max(size_x, size_y) <= BOX_MAX_MM):
        return None
    cu, cv_ = x + (bw - 1) / 2, y + (bh - 1) / 2
    center = (a * cu + b * cv_ + c, d * cu + e * cv_ + f)
    return {"center": [round(center[0]), round(center[1])], "size": sorted([round(size_x), round(size_y)]),
            "rotation": 0 if size_y >= size_x else 90}


def _paper(binary: np.ndarray):
    return cv2.connectedComponentsWithStats((binary == 0).astype(np.uint8), connectivity=4)


def snap_box(binary: np.ndarray, px_to_mm: list[float], at) -> dict | None:
    """{"center": [x, y], "size": [short, long] mm, "rotation": 0 | 90} of the closed region around `at`.

    Rotation 0: the long side runs along y, as a template's depth does; 90: along x."""
    u, v = (round(c) for c in px_from_mm(px_to_mm)(*at))
    h, w = binary.shape[:2]
    if not (0 <= u < w and 0 <= v < h) or binary[v, u] > 0:
        return None
    _, labels, stats, _ = _paper(binary)
    return _box(stats[labels[v, u]], px_to_mm, w, h)


def snap_boxes(binary: np.ndarray, px_to_mm: list[float], a, b) -> list[dict]:
    """Every rack-sized closed region whose centre lies inside the rectangle a-b (mm): a row traced in one pass."""
    to_px = px_from_mm(px_to_mm)
    (u0, v0), (u1, v1) = to_px(*a), to_px(*b)
    lo_u, hi_u, lo_v, hi_v = min(u0, u1), max(u0, u1), min(v0, v1), max(v0, v1)
    h, w = binary.shape[:2]
    n, _, stats, centroids = _paper(binary)
    out = []
    for k in range(1, n):
        cu, cv_ = centroids[k]
        if lo_u <= cu <= hi_u and lo_v <= cv_ <= hi_v and (box := _box(stats[k], px_to_mm, w, h)):
            out.append(box)
    return sorted(out, key=lambda r: (r["center"][1], r["center"][0]))
