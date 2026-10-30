"""Drawing fit (stage 8): does every wall lie on a line of the drawing?

The top-down IoU compares the model with the extractor's wall mask, so a human review that deletes false walls or
adds missed ones lowers it. Here the reference is the drawing's own ink. Every SAMPLE_MM along a wall, a sample hits
when a drawn line passes under either face or the centre line (single-line walls), within TOLERANCE_MM. Junctions
(inside another wall) and opening spans are skipped: the drawing has no wall line there. Ink includes text and
annotation lines, so a false wall drawn on an annotation line still fits: this catches walls placed where nothing is
drawn, and a model whose scale or offset is off (Gatsu GT 0.93; shifted 300 mm 0.71; scaled +1% 0.84).
"""

import math

import cv2
import numpy as np
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep

from core.spec.models import Spec

TOLERANCE_MM = 50
SAMPLE_MM = 50
OFF_SHARE = 0.5  # a wall with fewer of its samples on the drawing is listed
OFF_MIN_SAMPLES = 5


def drawing_fit(spec: Spec, gray: np.ndarray) -> dict:
    """{"fit": share of wall samples on drawn lines | None, "walls_off": [ids], "checked": walls, "tolerance_mm"}"""
    out = {"fit": None, "walls_off": [], "checked": 0, "tolerance_mm": TOLERANCE_MM}
    t = spec.meta.px_to_mm
    det = t[0] * t[4] - t[1] * t[3] if len(t) == 6 else 0
    if not det or gray is None:
        return out
    a, b, c, d, e, f = t
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    r = max(1, math.ceil(TOLERANCE_MM / math.sqrt(abs(det))))
    ink = cv2.dilate(ink, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) > 0
    h, w = ink.shape

    def on_ink(x: float, y: float) -> bool:
        x0, y0 = x - c, y - f
        u, v = round((e * x0 - b * y0) / det), round((-d * x0 + a * y0) / det)
        return 0 <= u < w and 0 <= v < h and bool(ink[v, u])

    feet = {x.id: LineString([x.a, x.b]).buffer(x.thickness / 2, cap_style="flat") for x in spec.walls
            if math.dist(x.a, x.b) > 0}
    hits = total = 0
    for wall in spec.walls:
        length = math.dist(wall.a, wall.b)
        if wall.id not in feet:
            continue
        ux, uy = (wall.b[0] - wall.a[0]) / length, (wall.b[1] - wall.a[1]) / length
        others = prep(unary_union([p for i, p in feet.items() if i != wall.id]).buffer(-1))
        spans = [(o.offset, o.offset + o.width) for o in spec.openings if o.wall_id == wall.id]
        half = wall.thickness / 2
        hit = n = 0
        for k in range(int(length // SAMPLE_MM) + 1):
            s = min(length, (k + 0.5) * SAMPLE_MM)
            if any(s0 <= s <= s1 for s0, s1 in spans):
                continue
            cx, cy = wall.a[0] + ux * s, wall.a[1] + uy * s
            if others.contains(Point(cx, cy)):
                continue
            n += 1
            hit += any(on_ink(cx - uy * o, cy + ux * o) for o in (-half, 0, half))
        if not n:
            continue
        out["checked"] += 1
        hits, total = hits + hit, total + n
        if n >= OFF_MIN_SAMPLES and hit / n < OFF_SHARE:
            out["walls_off"].append(wall.id)
    out["fit"] = round(hits / total, 4) if total else None
    return out
