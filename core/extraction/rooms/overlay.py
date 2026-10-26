"""Room overlay for the stage-4 panel, drawn on the working page (spec mm mapped back to working px)."""

from collections.abc import Callable

import cv2
import numpy as np
from shapely.geometry import Polygon as SPolygon

from core.spec.models import Spec

PALETTE = [(180, 119, 31), (14, 127, 255), (44, 160, 44), (40, 39, 214), (189, 103, 148), (75, 86, 140),
           (194, 119, 227), (34, 189, 188), (207, 190, 23)]  # BGR


def px_from_mm(px_to_mm: list[float]) -> Callable[[float, float], tuple[float, float]]:
    """Inverse of the px -> mm affine [a, b, c, d, e, f]."""
    a, b, c, d, e, f = px_to_mm
    det = a * e - b * d
    return lambda x, y: ((e * (x - c) - b * (y - f)) / det, (a * (y - f) - d * (x - c)) / det)


def _pts(ring, to_px) -> np.ndarray:
    return np.array([[round(v) for v in to_px(x, y)] for x, y in ring], np.int32)


def render_rooms_overlay(page_gray: np.ndarray, spec: Spec, to_px) -> np.ndarray:
    base = cv2.cvtColor(page_gray, cv2.COLOR_GRAY2BGR)
    fill = base.copy()
    for i, r in enumerate(spec.rooms):
        cv2.fillPoly(fill, [_pts(r.polygon, to_px)], PALETTE[i % len(PALETTE)])
    out = cv2.addWeighted(fill, 0.3, base, 0.7, 0)
    for i, r in enumerate(spec.rooms):
        cv2.polylines(out, [_pts(r.polygon, to_px)], True, PALETTE[i % len(PALETTE)], 2)
        at = r.label_pos or SPolygon(r.polygon).representative_point().coords[0]
        u, v = (round(t) for t in to_px(*at))
        text = f"{r.id} {r.name or r.type}"
        cv2.putText(out, text, (u, v), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(out, text, (u, v), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    return out
