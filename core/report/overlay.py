"""Spec drawn over the source plan image (report section 3, ground-truth review)."""

import math
from pathlib import Path

import cv2
import numpy as np

from core.spec.derive import column_footprint, wall_footprint
from core.spec.models import Spec


def _to_px(spec: Spec) -> np.ndarray:
    m = np.array(spec.meta.px_to_mm, dtype=float).reshape(2, 3)
    return cv2.invertAffineTransform(m)  # mm -> px


def render_overlay(spec: Spec, image_path: Path, out: Path) -> None:
    img = cv2.imread(str(image_path))
    inv = _to_px(spec)

    def px(points) -> np.ndarray:
        pts = np.array(points, dtype=float)
        return np.round(pts @ inv[:, :2].T + inv[:, 2]).astype(np.int32)

    h, w = img.shape[:2]
    for a in spec.grid.axes:  # grid axes, light blue
        if a.orientation == "vertical":
            p = px([(a.offset, -1e5), (a.offset, 1e5)])
        else:
            p = px([(-1e5, a.offset), (1e5, a.offset)])
        cv2.line(img, tuple(p[0]), tuple(p[1]), (230, 180, 120), 1)
    for r in spec.rooms:
        cv2.polylines(img, [px(r.polygon)], True, (80, 180, 80), 1)
        c = px([np.mean(r.polygon, axis=0)])[0]
        cv2.putText(img, r.id, tuple(c), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (40, 140, 40), 1)
    for wall in spec.walls:
        cv2.polylines(img, [px(wall_footprint(wall, spec).exterior.coords)], True, (255, 0, 255), 1)
    for col in spec.columns:
        cv2.polylines(img, [px(column_footprint(col).exterior.coords)], True, (255, 255, 0), 1)
    walls = {x.id: x for x in spec.walls}
    for o in spec.openings:
        wl = walls.get(o.wall_id)
        if not wl:
            continue
        length = math.hypot(wl.b[0] - wl.a[0], wl.b[1] - wl.a[1])
        ux, uy = (wl.b[0] - wl.a[0]) / length, (wl.b[1] - wl.a[1]) / length
        seg = px([(wl.a[0] + ux * o.offset, wl.a[1] + uy * o.offset),
                  (wl.a[0] + ux * (o.offset + o.width), wl.a[1] + uy * (o.offset + o.width))])
        cv2.line(img, tuple(seg[0]), tuple(seg[1]), (0, 140, 255) if o.category == "door" else (255, 120, 0), 2)
    for st in spec.stairs:
        for f in st.flights:
            seg = px([f.start, f.end])
            cv2.arrowedLine(img, tuple(seg[0]), tuple(seg[1]), (0, 0, 255), 1, tipLength=0.15)
    assert img.shape[:2] == (h, w)
    cv2.imwrite(str(out), img)
