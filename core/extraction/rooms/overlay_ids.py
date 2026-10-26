"""Numbered overlay for stage 5 and the Review tab (PRD/04 Tahap 5 langkah 5): walls blue, doors green, columns
orange, rooms lightly tinted per room, ID labels >= 14 px on a contrasting background. One RGBA layer per type."""

import math

import cv2
import numpy as np
from shapely.geometry import Polygon as SPolygon

from core.extraction.rooms.overlay import PALETTE
from core.spec.derive import column_footprint, wall_footprint
from core.spec.models import Spec

BLUE, GREEN, ORANGE = (255, 90, 15), (40, 170, 40), (0, 140, 255)  # BGR
FONT, SCALE = cv2.FONT_HERSHEY_SIMPLEX, 0.65  # cap height ~14 px


def _pts(coords, to_px) -> np.ndarray:
    return np.array([[round(v) for v in to_px(x, y)] for x, y in coords], np.int32)


def _label(layer: np.ndarray, text: str, at: tuple[float, float], colour) -> None:
    (w, h), base = cv2.getTextSize(text, FONT, SCALE, 1)
    u, v = round(at[0] - w / 2), round(at[1] + h / 2)
    cv2.rectangle(layer, (u - 2, v - h - 3), (u + w + 2, v + base), (255, 255, 255, 235), -1)
    cv2.putText(layer, text, (u, v), FONT, SCALE, (*colour, 255), 1, cv2.LINE_AA)


def render_ids_overlay(page_gray: np.ndarray, spec: Spec, to_px) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    h, w = page_gray.shape
    layers = {k: np.zeros((h, w, 4), np.uint8) for k in ("rooms", "walls", "doors", "columns")}
    for i, r in enumerate(spec.rooms):
        colour = PALETTE[i % len(PALETTE)]
        cv2.fillPoly(layers["rooms"], [_pts(r.polygon, to_px)], (*colour, 60))
        at = r.label_pos or SPolygon(r.polygon).representative_point().coords[0]
        _label(layers["rooms"], r.id, to_px(*at), colour)
    for wl in spec.walls:
        fp = wall_footprint(wl, spec)
        if not fp.is_empty:
            cv2.fillPoly(layers["walls"], [_pts(fp.exterior.coords, to_px)], (*BLUE, 200))
        _label(layers["walls"], wl.id, to_px((wl.a[0] + wl.b[0]) / 2, (wl.a[1] + wl.b[1]) / 2), BLUE)
    walls = {wl.id: wl for wl in spec.walls}
    for o in spec.openings:
        wl = walls.get(o.wall_id)
        if not wl:
            continue
        length = math.dist(wl.a, wl.b) or 1.0
        ux, uy = (wl.b[0] - wl.a[0]) / length, (wl.b[1] - wl.a[1]) / length
        p = (wl.a[0] + ux * o.offset, wl.a[1] + uy * o.offset)
        q = (p[0] + ux * o.width, p[1] + uy * o.width)
        cv2.line(layers["doors"], tuple(_pts([p], to_px)[0]), tuple(_pts([q], to_px)[0]), (*GREEN, 255), 5)
        _label(layers["doors"], o.id, to_px((p[0] + q[0]) / 2, (p[1] + q[1]) / 2), GREEN)
    for c in spec.columns:
        cv2.fillPoly(layers["columns"], [_pts(column_footprint(c).exterior.coords, to_px)], (*ORANGE, 220))
        _label(layers["columns"], c.id, to_px(*c.center), ORANGE)
    out = cv2.cvtColor(page_gray, cv2.COLOR_GRAY2BGR).astype(np.float32)
    for k in ("rooms", "walls", "doors", "columns"):
        a = layers[k][:, :, 3:4].astype(np.float32) / 255
        out = out * (1 - a) + layers[k][:, :, :3].astype(np.float32) * a
    return out.astype(np.uint8), layers
