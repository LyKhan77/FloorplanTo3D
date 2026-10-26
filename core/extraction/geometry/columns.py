"""Columns and pilasters (PRD/04 §3.3, FR-EX-17). Working pixels; centres are converted to mm by the candidate.

Gatsu draws columns as a square box with an H symbol inside. The box outline merges into the wall lines, but its
inner boundary is still a closed hole contour, so holes are the main cue. Filled square blobs (the symbol mask)
are the other.
"""

import math

import cv2
import numpy as np
from shapely.geometry import LineString, box

SIDE_MM = (150, 800)
PILASTER_SIDE_MM = (300, 1400)  # fins are ~500 x 1300; 150-300 mm holes are the inside of double-line walls
NEAR_CROSSING_MM = 300
FILL_MIN = 0.75
OFF_GRID_CONF = 0.5  # off the grid only the shape speaks for a column: always reviewed (< 0.6)


def _crossings(axes: list[dict]) -> list[tuple[float, float, str, str]]:
    v = [a for a in axes if a["orientation"] == "vertical"]
    h = [a for a in axes if a["orientation"] == "horizontal"]
    return [(x["px"], y["px"], x["id"], y["id"]) for x in v for y in h]  # grid_ref holds axis ids (PRD/03)


def _nearest_crossing(cx: float, cy: float, crossings, s: float):
    best = min(crossings, key=lambda c: math.hypot(c[0] - cx, c[1] - cy), default=None)
    if best and math.hypot(best[0] - cx, best[1] - cy) * s <= NEAR_CROSSING_MM:
        return best
    return None


def _on_wall(rect, walls: list[dict], s: float, tol_mm: float = 0) -> bool:
    b = box(*rect)
    return any(LineString([w["p0"], w["p1"]]).distance(b) <= w["thickness_mm"] / s / 2 + tol_mm / s for w in walls)


def _holes(clean: np.ndarray) -> list[tuple[float, float, float, float, float]]:
    """(x0, y0, x1, y1, fill ratio) of hole contours (inner boundaries)."""
    contours, hierarchy = cv2.findContours(clean, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    if hierarchy is None:
        return out
    for cnt, (_, _, _, parent) in zip(contours, hierarchy[0], strict=True):
        if parent == -1:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 3 or h < 3:
            continue
        out.append((x, y, x + w, y + h, cv2.contourArea(cnt) / (w * h)))
    return sorted(out)


def _col(cx, cy, size_mm, shape, kind, conf, ref) -> dict:
    return {"center_px": [round(cx, 2), round(cy, 2)], "size_mm": [round(size_mm[0]), round(size_mm[1])],
            "shape": shape, "rotation": 0, "kind": kind, "confidence": conf, "grid_ref": list(ref) if ref else None}


def find_columns(clean: np.ndarray, symbol_mask: np.ndarray, axes: list[dict], walls: list[dict], s: float) -> list[dict]:
    crossings = _crossings(axes)
    sw = 2.0
    cands = []
    holes = _holes(clean)
    used = set()
    for vx, hy, vl, hl in crossings:  # (b)/(c) at a crossing: the box may be split by the H or an axis line
        near = [i for i, (x0, y0, x1, y1, _) in enumerate(holes)
                if math.hypot((x0 + x1) / 2 - vx, (y0 + y1) / 2 - hy) * s <= NEAR_CROSSING_MM
                and max(x1 - x0, y1 - y0) * s <= SIDE_MM[1]]
        if not near:
            continue
        x0, y0 = min(holes[i][0] for i in near), min(holes[i][1] for i in near)
        x1, y1 = max(holes[i][2] for i in near), max(holes[i][3] for i in near)
        w_mm, h_mm = (x1 - x0 + 2 * sw) * s, (y1 - y0 + 2 * sw) * s
        if not all(SIDE_MM[0] <= v <= SIDE_MM[1] for v in (w_mm, h_mm)) or max(w_mm, h_mm) / min(w_mm, h_mm) > 1.5:
            continue
        used.update(near)
        inside = clean[int(y0) + 1:int(y1) - 1, int(x0) + 1:int(x1) - 1]
        shape = "h_section" if inside.size and (inside > 0).mean() > 0.03 else "rect"
        cands.append(_col((x0 + x1) / 2, (y0 + y1) / 2, (w_mm, h_mm), shape, "structural", 0.9, (vl, hl)))
    for i, (x0, y0, x1, y1, fill) in enumerate(holes):  # off the grid: a clean hollow square with a symbol, on a wall
        if i in used:
            continue
        w_mm, h_mm = (x1 - x0 + 2 * sw) * s, (y1 - y0 + 2 * sw) * s
        if fill < FILL_MIN or not all(SIDE_MM[0] <= v <= SIDE_MM[1] for v in (w_mm, h_mm)) \
                or max(w_mm, h_mm) / min(w_mm, h_mm) > 1.5:
            continue
        inside = clean[int(y0) + 1:int(y1) - 1, int(x0) + 1:int(x1) - 1]
        if inside.size and (inside > 0).mean() > 0.03 and _on_wall((x0, y0, x1, y1), walls, s) \
                and not _nearest_crossing((x0 + x1) / 2, (y0 + y1) / 2, crossings, s):
            cands.append(_col((x0 + x1) / 2, (y0 + y1) / 2, (w_mm, h_mm), "h_section", "structural", OFF_GRID_CONF, None))
    n, _, stats, _ = cv2.connectedComponentsWithStats(symbol_mask, connectivity=8)
    for i in range(1, n):  # (a) filled blob
        x, y, w, h, area = (float(v) for v in stats[i])
        side = math.sqrt(area) * s
        if not SIDE_MM[0] <= side <= SIDE_MM[1] or max(w, h) / min(w, h) > 1.5 or area / (w * h) < 0.8:
            continue
        cx, cy = x + w / 2, y + h / 2
        cr = _nearest_crossing(cx, cy, crossings, s)
        if cr:
            cands.append(_col(cx, cy, (w * s, h * s), "rect", "structural", 0.9, cr[2:]))
        elif _on_wall((x, y, x + w, y + h), walls, s):  # free-standing filled squares are MEP symbols
            cands.append(_col(cx, cy, (w * s, h * s), "rect", "structural", OFF_GRID_CONF, None))
    out: list[dict] = []
    for c in sorted(cands, key=lambda c: (-c["confidence"], c["center_px"])):
        if all(math.dist(c["center_px"], o["center_px"]) * s > NEAR_CROSSING_MM for o in out):
            out.append(c)
    return sorted(out, key=lambda c: (c["center_px"][1], c["center_px"][0]))


def find_pilasters(clean: np.ndarray, walls: list[dict], axes: list[dict], s: float) -> list[dict]:
    """Small hollow rectangles (fins) next to an exterior wall, away from grid crossings."""
    crossings = _crossings(axes)
    exterior = [w for w in walls if w.get("kind") == "exterior"]
    sw = 2.0
    out = []
    for x0, y0, x1, y1, fill in _holes(clean):
        w_mm, h_mm = (x1 - x0 + 2 * sw) * s, (y1 - y0 + 2 * sw) * s
        if fill < FILL_MIN or not all(PILASTER_SIDE_MM[0] <= v <= PILASTER_SIDE_MM[1] for v in (w_mm, h_mm)) \
                or max(w_mm, h_mm) / min(w_mm, h_mm) > 4:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if _nearest_crossing(cx, cy, crossings, s) or not _on_wall((x0, y0, x1, y1), exterior, s, 300):
            continue
        out.append(_col(cx, cy, (w_mm, h_mm), "rect", "pilaster", 0.7, None))
    return out


def _col_box(c: dict, s: float, margin_mm: float = 100) -> tuple[float, float, float, float]:
    hw, hh = (c["size_mm"][0] / 2 + margin_mm) / s, (c["size_mm"][1] / 2 + margin_mm) / s
    x, y = c["center_px"]
    return x - hw, y - hh, x + hw, y + hh


def drop_at_columns(walls: list[dict], doors: list[dict], columns: list[dict], s: float) -> tuple[list[dict], list[dict]]:
    """Walls lying inside a column box (its outline read as wall lines) are dropped, and arc-less gap openings
    that touch a column or pilaster are a wall ending at a column, not a doorway. Door wall indices are remapped."""
    boxes = [box(*_col_box(c, s)) for c in columns]
    keep_idx = [i for i, w in enumerate(walls) if not any(b.contains(LineString([w["p0"], w["p1"]])) for b in boxes)]
    remap = {old: new for new, old in enumerate(keep_idx)}
    kept_doors = []
    for d in doors:
        if d["wall"] not in remap:
            continue
        w = walls[d["wall"]]
        if d["door_type"] in ("opening", "sliding"):
            lo, hi = w["a"] + d["offset"] / s, w["a"] + (d["offset"] + d["width"]) / s
            seg = LineString([(lo, w["c"]), (hi, w["c"])] if w["orient"] == "h" else [(w["c"], lo), (w["c"], hi)])
            if any(b.distance(seg) <= 100 / s for b in boxes):
                continue
        kept_doors.append({**d, "wall": remap[d["wall"]]})
    return [walls[i] for i in keep_idx], kept_doors
